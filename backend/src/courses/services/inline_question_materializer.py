"""Materialize server-owned learning questions from lesson MDX."""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.courses.models import LearningQuestion
from src.courses.schemas import LessonDetailResponse


logger = logging.getLogger(__name__)


_SUPPORTED_COMPONENTS = {"LatexExpression", "FreeForm", "JXGBoard", "MultipleChoice", "FillInTheBlank"}
_COMPONENT_RE = re.compile(
    r"<(LatexExpression|FreeForm|JXGBoard|MultipleChoice|FillInTheBlank)\b(?P<attrs>[^>]*)/?>",
    re.DOTALL,
)
_ATTR_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_HIDDEN_PROPS = {
    "expectedLatex",
    "expectedAnswer",
    "sampleAnswer",
    "solutionLatex",
    "expectedState",
    "correctAnswer",
    "answer",
    "explanation",
    "tolerance",
    "perCheckTolerance",
}


@dataclass(frozen=True)
class _Attribute:
    name: str
    raw_value: str
    value: Any
    start: int
    end: int


@dataclass(frozen=True)
class _InlineQuestion:
    question: str
    hints: list[str]
    grade_kind: str
    expected_payload: dict[str, Any]
    input_kind: str


class InlineQuestionMaterializer:
    """Create hidden learning-question rows and strip expected answers from MDX."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def materialize_lesson_response(
        self,
        *,
        lesson: LessonDetailResponse,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
    ) -> LessonDetailResponse:
        """Return a lesson response with inline questions bound to server-owned IDs."""
        content = lesson.content
        sanitized_content = content
        if content:
            sanitized_content = await self._materialize_content(
                content=content,
                user_id=user_id,
                course_id=course_id,
                lesson_id=lesson.id,
                concept_id=lesson.concept_id,
                lesson_version_id=lesson.version_id,
                scope="content",
            )
        sanitized_windows = []
        for window in lesson.windows:
            sanitized_window_content = await self._materialize_content(
                content=window.content,
                user_id=user_id,
                course_id=course_id,
                lesson_id=lesson.id,
                concept_id=lesson.concept_id,
                lesson_version_id=lesson.version_id,
                scope=f"window:{window.window_index}",
            )
            sanitized_windows.append(window.model_copy(update={"content": sanitized_window_content}))

        return lesson.model_copy(update={"content": sanitized_content, "windows": sanitized_windows})

    async def _materialize_content(
        self,
        *,
        content: str,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
        concept_id: uuid.UUID | None,
        lesson_version_id: uuid.UUID | None,
        scope: str,
    ) -> str:
        pieces: list[str] = []
        cursor = 0
        for index, match in enumerate(_COMPONENT_RE.finditer(content)):
            pieces.append(content[cursor : match.start()])
            component = match.group(1)
            raw_attrs = match.group("attrs")
            replacement = match.group(0)
            try:
                attrs = _parse_attributes(raw_attrs)
                inline_question = _build_inline_question(component=component, attrs=attrs)
                if inline_question is not None:
                    question_id = await self._upsert_question(
                        user_id=user_id,
                        course_id=course_id,
                        lesson_id=lesson_id,
                        concept_id=concept_id,
                        lesson_version_id=lesson_version_id,
                        source_component=component,
                        source_key=_source_key(scope=scope, index=index, component=component, attrs=attrs),
                        inline_question=inline_question,
                    )
                    replacement = _rewrite_component(match.group(0), raw_attrs=raw_attrs, attrs=attrs, question_id=question_id)
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                replacement = _strip_hidden_component(match.group(0), raw_attrs=raw_attrs)
                logger.warning(
                    "courses.inline_question.materialize_failed",
                    extra={"lesson_id": str(lesson_id), "component": component, "scope": scope, "error": str(error)},
                )
            pieces.append(replacement)
            cursor = match.end()
        pieces.append(content[cursor:])
        return "".join(pieces)

    async def _upsert_question(
        self,
        *,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
        concept_id: uuid.UUID | None,
        lesson_version_id: uuid.UUID | None,
        source_component: str,
        source_key: str,
        inline_question: _InlineQuestion,
    ) -> uuid.UUID:
        if concept_id is None:
            detail = "lesson concept is required for inline practice"
            raise ValueError(detail)
        existing = await self._session.scalar(
            select(LearningQuestion).where(
                LearningQuestion.user_id == user_id,
                LearningQuestion.course_id == course_id,
                LearningQuestion.lesson_id == lesson_id,
                LearningQuestion.lesson_version_id == lesson_version_id,
                LearningQuestion.source_key == source_key,
            )
        )
        question_payload = {"inputKind": inline_question.input_kind, "hints": inline_question.hints}
        if existing is not None:
            existing.question = inline_question.question
            existing.grade_kind = inline_question.grade_kind
            existing.expected_payload = inline_question.expected_payload
            existing.question_payload = question_payload
            existing.source_component = source_component
            await self._session.flush()
            return existing.id

        question = LearningQuestion(
            user_id=user_id,
            course_id=course_id,
            concept_id=concept_id,
            lesson_id=lesson_id,
            lesson_version_id=lesson_version_id,
            question=inline_question.question,
            expected_answer=inline_question.expected_payload.get("expectedAnswer"),
            answer_kind=inline_question.input_kind if inline_question.input_kind in {"text", "math_latex"} else None,
            grade_kind=inline_question.grade_kind,
            expected_payload=inline_question.expected_payload,
            question_payload=question_payload,
            hints=inline_question.hints,
            structure_signature=source_key,
            predicted_p_correct=0.5,
            target_probability=0.5,
            target_low=0.0,
            target_high=1.0,
            core_model="lesson_inline",
            practice_context=inline_question.expected_payload.get("practiceContext", "inline"),
            source_component=source_component,
            source_key=source_key,
        )
        self._session.add(question)
        await self._session.flush()
        return question.id


def _parse_attributes(raw_attrs: str) -> dict[str, _Attribute]:
    attrs: dict[str, _Attribute] = {}
    cursor = 0
    while cursor < len(raw_attrs):
        match = _ATTR_NAME_RE.search(raw_attrs, cursor)
        if match is None:
            break
        name = match.group(0)
        equals_index = _skip_space(raw_attrs, match.end())
        if equals_index >= len(raw_attrs) or raw_attrs[equals_index] != "=":
            cursor = match.end()
            continue
        value_start = _skip_space(raw_attrs, equals_index + 1)
        raw_value, end = _read_raw_value(raw_attrs, value_start)
        attrs[name] = _Attribute(name=name, raw_value=raw_value, value=_parse_value(raw_value), start=match.start(), end=end)
        cursor = end
    return attrs


def _skip_space(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def _read_raw_value(text: str, start: int) -> tuple[str, int]:
    if start >= len(text):
        detail = "missing attribute value"
        raise ValueError(detail)
    quote = text[start]
    if quote in {'"', "'"}:
        end = start + 1
        while end < len(text):
            if text[end] == quote and text[end - 1] != "\\":
                return text[start : end + 1], end + 1
            end += 1
        detail = "unterminated quoted attribute"
        raise ValueError(detail)
    if quote == "{":
        depth = 1
        end = start + 1
        while end < len(text) and depth > 0:
            if text[end] == "{":
                depth += 1
            elif text[end] == "}":
                depth -= 1
            end += 1
        if depth != 0:
            detail = "unterminated expression attribute"
            raise ValueError(detail)
        return text[start:end], end
    end = start
    while end < len(text) and not text[end].isspace():
        end += 1
    return text[start:end], end


def _parse_value(raw_value: str) -> Any:
    if raw_value.startswith(("'", '"')):
        return ast.literal_eval(raw_value)
    if raw_value.startswith("{") and raw_value.endswith("}"):
        inner = raw_value[1:-1].strip()
        if not inner:
            return None
        try:
            return json.loads(inner)
        except json.JSONDecodeError:
            return ast.literal_eval(_pythonize_js_object_literal(inner))
    return raw_value


def _pythonize_js_object_literal(value: str) -> str:
    """Quote JSX-style object keys so Python can parse the literal."""
    text = _replace_js_literals(value)
    pieces: list[str] = []
    cursor = 0
    quote: str | None = None
    while cursor < len(text):
        char = text[cursor]
        if quote is not None:
            pieces.append(char)
            if char == quote and text[cursor - 1] != "\\":
                quote = None
            cursor += 1
            continue

        if char in {'"', "'"}:
            quote = char
            pieces.append(char)
            cursor += 1
            continue

        if char.isalpha() or char == "_":
            end = cursor + 1
            while end < len(text) and (text[end].isalnum() or text[end] == "_"):
                end += 1
            next_index = _skip_space(text, end)
            if next_index < len(text) and text[next_index] == ":" and _is_object_key_position(text, cursor):
                pieces.append(repr(text[cursor:end]))
                cursor = end
                continue

        pieces.append(char)
        cursor += 1
    return "".join(pieces)


def _replace_js_literals(value: str) -> str:
    replacements = {"true": "True", "false": "False", "null": "None"}
    pattern = re.compile(r"\b(true|false|null)\b")
    return pattern.sub(lambda match: replacements[match.group(1)], value)


def _is_object_key_position(text: str, index: int) -> bool:
    previous = index - 1
    while previous >= 0 and text[previous].isspace():
        previous -= 1
    return previous < 0 or text[previous] in "{,"


def _build_inline_question(component: str, attrs: dict[str, _Attribute]) -> _InlineQuestion | None:  # noqa: PLR0911
    if component not in _SUPPORTED_COMPONENTS:
        return None
    question = _string_attr(attrs, "question") or _string_attr(attrs, "sentence") or "Practice question"
    hints = _list_attr(attrs, "hints")
    practice_context = _string_attr(attrs, "practiceContext") or "inline"
    criteria = _string_attr(attrs, "criteria")

    if component == "LatexExpression":
        expected_latex = _string_attr(attrs, "expectedLatex") or _string_attr(attrs, "solutionLatex")
        if not expected_latex:
            return None
        return _InlineQuestion(
            question=question,
            hints=hints,
            grade_kind="latex_expression",
            input_kind="math_latex",
            expected_payload={"expectedLatex": expected_latex, "criteria": criteria, "practiceContext": practice_context},
        )
    if component == "JXGBoard":
        expected_state = attrs.get("expectedState")
        if expected_state is None or not isinstance(expected_state.value, dict):
            return None
        return _InlineQuestion(
            question=question,
            hints=hints,
            grade_kind="jxg_state",
            input_kind="jxg_state",
            expected_payload={
                "expectedState": expected_state.value,
                "tolerance": _number_attr(attrs, "tolerance"),
                "perCheckTolerance": _dict_attr(attrs, "perCheckTolerance"),
                "criteria": criteria,
                "practiceContext": practice_context,
            },
        )
    if component == "MultipleChoice":
        options = _list_attr(attrs, "options")
        correct_index = _int_attr(attrs, "correctAnswer")
        if correct_index is None or correct_index < 0 or correct_index >= len(options):
            return None
        return _InlineQuestion(
            question=question,
            hints=hints,
            grade_kind="practice_answer",
            input_kind="text",
            expected_payload={
                "expectedAnswer": options[correct_index],
                "answerKind": "text",
                "criteria": criteria,
                "practiceContext": practice_context,
            },
        )
    if component == "FillInTheBlank":
        expected_blank = _string_attr(attrs, "answer") or _string_attr(attrs, "expectedAnswer")
        if not expected_blank:
            return None
        return _InlineQuestion(
            question=question,
            hints=hints,
            grade_kind="practice_answer",
            input_kind="text",
            expected_payload={
                "expectedAnswer": expected_blank,
                "answerKind": "text",
                "criteria": criteria,
                "practiceContext": practice_context,
            },
        )

    expected_answer = _string_attr(attrs, "expectedAnswer") or _string_attr(attrs, "sampleAnswer")
    if not expected_answer:
        return None
    answer_kind = _string_attr(attrs, "answerKind") or "text"
    return _InlineQuestion(
        question=question,
        hints=hints,
        grade_kind="practice_answer",
        input_kind=answer_kind,
        expected_payload={
            "expectedAnswer": expected_answer,
            "answerKind": answer_kind,
            "criteria": criteria,
            "practiceContext": practice_context,
        },
    )


def _string_attr(attrs: dict[str, _Attribute], name: str) -> str | None:
    attr = attrs.get(name)
    value = attr.value if attr is not None else None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _number_attr(attrs: dict[str, _Attribute], name: str) -> float | None:
    attr = attrs.get(name)
    value = attr.value if attr is not None else None
    if isinstance(value, int | float):
        return float(value)
    return None


def _int_attr(attrs: dict[str, _Attribute], name: str) -> int | None:
    attr = attrs.get(name)
    value = attr.value if attr is not None else None
    if isinstance(value, int):
        return value
    return None


def _dict_attr(attrs: dict[str, _Attribute], name: str) -> dict[str, Any] | None:
    attr = attrs.get(name)
    value = attr.value if attr is not None else None
    if isinstance(value, dict):
        return value
    return None


def _list_attr(attrs: dict[str, _Attribute], name: str) -> list[str]:
    attr = attrs.get(name)
    value = attr.value if attr is not None else None
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _source_key(*, scope: str, index: int, component: str, attrs: dict[str, _Attribute]) -> str:
    question = _string_attr(attrs, "question") or ""
    digest = hashlib.sha256(f"{scope}:{index}:{component}:{question}".encode()).hexdigest()
    return f"inline:{digest}"


def _rewrite_component(tag: str, *, raw_attrs: str, attrs: dict[str, _Attribute], question_id: uuid.UUID) -> str:
    cleaned_attrs = raw_attrs
    for attr in sorted(attrs.values(), key=lambda item: item.start, reverse=True):
        if attr.name in _HIDDEN_PROPS or attr.name == "questionId":
            cleaned_attrs = f"{cleaned_attrs[: attr.start]}{cleaned_attrs[attr.end :]}"
    cleaned_attrs = cleaned_attrs.strip()
    closing = "/>" if tag.rstrip().endswith("/>") else ">"
    if cleaned_attrs.endswith("/"):
        cleaned_attrs = cleaned_attrs[:-1].rstrip()
    prefix = tag[: tag.find(raw_attrs)].rstrip()
    visible_attrs = f" {cleaned_attrs}" if cleaned_attrs else ""
    question_attr = f' questionId="{question_id}"'
    return f"{prefix}{visible_attrs}{question_attr}{closing}"


def _strip_hidden_component(tag: str, *, raw_attrs: str) -> str:
    cleaned_attrs = _remove_hidden_attrs(raw_attrs).strip()
    closing = "/>" if tag.rstrip().endswith("/>") else ">"
    if cleaned_attrs.endswith("/"):
        cleaned_attrs = cleaned_attrs[:-1].rstrip()
    prefix = tag[: tag.find(raw_attrs)].rstrip()
    visible_attrs = f" {cleaned_attrs}" if cleaned_attrs else ""
    return f"{prefix}{visible_attrs}{closing}"


def _remove_hidden_attrs(raw_attrs: str) -> str:
    spans: list[tuple[int, int]] = []
    cursor = 0
    while cursor < len(raw_attrs):
        match = _ATTR_NAME_RE.search(raw_attrs, cursor)
        if match is None:
            break
        name = match.group(0)
        equals_index = _skip_space(raw_attrs, match.end())
        if equals_index >= len(raw_attrs) or raw_attrs[equals_index] != "=":
            cursor = match.end()
            continue
        value_start = _skip_space(raw_attrs, equals_index + 1)
        try:
            _, end = _read_raw_value(raw_attrs, value_start)
        except ValueError:
            end = _next_attr_boundary(raw_attrs, value_start)
        if name in _HIDDEN_PROPS or name == "questionId":
            spans.append((match.start(), end))
        cursor = end
    cleaned = raw_attrs
    for start, end in sorted(spans, reverse=True):
        cleaned = f"{cleaned[:start]}{cleaned[end:]}"
    return cleaned


def _next_attr_boundary(raw_attrs: str, start: int) -> int:
    end = start
    while end < len(raw_attrs) and not raw_attrs[end].isspace():
        end += 1
    return end
