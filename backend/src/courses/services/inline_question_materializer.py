"""Materialize server-owned learning questions from lesson MDX."""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.courses.models import LearningQuestion
from src.courses.schemas import LessonDetailResponse


_SUPPORTED_COMPONENTS = {"LatexExpression", "FreeForm", "JXGBoard", "MultipleChoice", "FillInTheBlank"}
_REPO_ROOT = Path(__file__).resolve().parents[4]
_WEB_DIR = _REPO_ROOT / "web"
_MDX_MATERIALIZER_SCRIPT = _WEB_DIR / "scripts" / "materialize-inline-questions.mjs"


@dataclass(frozen=True)
class _MdxDocument:
    key: str
    scope: str
    content: str


@dataclass(frozen=True)
class _ExtractedComponent:
    component: str
    index: int
    placeholder: str
    attrs: dict[str, Any]


@dataclass(frozen=True)
class _InlineQuestion:
    question: str
    hints: list[str]
    grade_kind: str
    expected_answer: str | None
    answer_kind: str | None
    expected_payload: dict[str, Any]
    practice_context: str


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
        documents: list[_MdxDocument] = []
        if lesson.content:
            documents.append(_MdxDocument(key="content", scope="content", content=lesson.content))
        documents.extend(
            _MdxDocument(
                key=f"window:{window.window_index}",
                scope=f"window:{window.window_index}",
                content=window.content,
            )
            for window in lesson.windows
        )

        materialized_documents = await self._materialize_documents(
            documents=documents,
            user_id=user_id,
            course_id=course_id,
            lesson_id=lesson.id,
            concept_id=lesson.concept_id,
            lesson_version_id=lesson.version_id,
        )
        sanitized_content = materialized_documents.get("content", lesson.content)
        sanitized_windows = []
        for window in lesson.windows:
            sanitized_window_content = materialized_documents.get(f"window:{window.window_index}", window.content)
            sanitized_windows.append(window.model_copy(update={"content": sanitized_window_content}))

        return lesson.model_copy(update={"content": sanitized_content, "windows": sanitized_windows})

    async def _materialize_documents(
        self,
        *,
        documents: list[_MdxDocument],
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
        concept_id: uuid.UUID | None,
        lesson_version_id: uuid.UUID | None,
    ) -> dict[str, str]:
        if not documents:
            return {}

        parsed_documents = await _parse_mdx_documents(documents)
        materialized_documents: dict[str, str] = {}
        for document in parsed_documents:
            content = str(document["content"])
            for component in _extracted_components(document):
                inline_question = _build_inline_question(component=component.component, attrs=component.attrs)
                if inline_question is None:
                    content = _remove_placeholder_question_id(content, component.placeholder)
                    continue
                question_id = await self._upsert_question(
                    user_id=user_id,
                    course_id=course_id,
                    lesson_id=lesson_id,
                    concept_id=concept_id,
                    lesson_version_id=lesson_version_id,
                    source_component=component.component,
                    source_key=_source_key(
                        scope=str(document["scope"]),
                        index=component.index,
                        component=component.component,
                        attrs=component.attrs,
                    ),
                    inline_question=inline_question,
                )
                content = content.replace(component.placeholder, str(question_id))
            materialized_documents[str(document["key"])] = content
        return materialized_documents

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
        question_payload = {"answerKind": inline_question.answer_kind, "hints": inline_question.hints}
        if existing is not None:
            existing.question = inline_question.question
            existing.expected_answer = inline_question.expected_answer
            existing.answer_kind = inline_question.answer_kind
            existing.grade_kind = inline_question.grade_kind
            existing.expected_payload = inline_question.expected_payload
            existing.question_payload = question_payload
            existing.practice_context = inline_question.practice_context
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
            expected_answer=inline_question.expected_answer,
            answer_kind=inline_question.answer_kind,
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
            practice_context=inline_question.practice_context,
            source_component=source_component,
            source_key=source_key,
        )
        self._session.add(question)
        await self._session.flush()
        return question.id


async def _parse_mdx_documents(documents: list[_MdxDocument]) -> list[dict[str, Any]]:
    payload = {"documents": [{"key": document.key, "content": document.content} for document in documents]}
    process = await asyncio.create_subprocess_exec(
        "node",
        str(_MDX_MATERIALIZER_SCRIPT),
        cwd=str(_WEB_DIR),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate(json.dumps(payload).encode())
    if process.returncode != 0:
        detail = stderr.decode().strip() or "MDX materializer failed"
        raise ValueError(detail)
    try:
        response = json.loads(stdout.decode())
    except json.JSONDecodeError as error:
        detail = f"invalid MDX materializer response: {error}"
        raise ValueError(detail) from error

    response_documents = response.get("documents")
    if not isinstance(response_documents, list):
        detail = "invalid MDX materializer response: missing documents"
        raise TypeError(detail)
    scope_by_key = {document.key: document.scope for document in documents}
    for response_document in response_documents:
        key = str(response_document.get("key"))
        response_document["scope"] = scope_by_key[key]
    return response_documents


def _extracted_components(document: dict[str, Any]) -> list[_ExtractedComponent]:
    components = document.get("components")
    if not isinstance(components, list):
        return []
    extracted_components: list[_ExtractedComponent] = []
    for component in components:
        if not isinstance(component, dict):
            continue
        component_name = str(component.get("component"))
        if component_name not in _SUPPORTED_COMPONENTS:
            continue
        attrs = component.get("attrs")
        extracted_components.append(
            _ExtractedComponent(
                component=component_name,
                index=_int_value(component.get("index")) or 0,
                placeholder=str(component.get("placeholder")),
                attrs=attrs if isinstance(attrs, dict) else {},
            )
        )
    return extracted_components


def _build_inline_question(component: str, attrs: dict[str, Any]) -> _InlineQuestion | None:  # noqa: PLR0911
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
            expected_answer=expected_latex,
            answer_kind="latex",
            expected_payload={"expectedLatex": expected_latex, "criteria": criteria},
            practice_context=practice_context,
        )
    if component == "JXGBoard":
        expected_state = _dict_attr(attrs, "expectedState")
        if expected_state is None:
            return None
        return _InlineQuestion(
            question=question,
            hints=hints,
            grade_kind="jxg_state",
            expected_answer=None,
            answer_kind=None,
            expected_payload={
                "expectedState": expected_state,
                "tolerance": _number_attr(attrs, "tolerance"),
                "perCheckTolerance": _dict_attr(attrs, "perCheckTolerance"),
                "criteria": criteria,
            },
            practice_context=practice_context,
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
            expected_answer=options[correct_index],
            answer_kind="text",
            expected_payload={"criteria": criteria},
            practice_context=practice_context,
        )
    if component == "FillInTheBlank":
        expected_blank = _string_attr(attrs, "answer") or _string_attr(attrs, "expectedAnswer")
        if not expected_blank:
            return None
        return _InlineQuestion(
            question=question,
            hints=hints,
            grade_kind="practice_answer",
            expected_answer=expected_blank,
            answer_kind="text",
            expected_payload={"criteria": criteria},
            practice_context=practice_context,
        )

    expected_answer = _string_attr(attrs, "expectedAnswer") or _string_attr(attrs, "sampleAnswer")
    if not expected_answer:
        return None
    answer_kind = _string_attr(attrs, "answerKind") or "text"
    return _InlineQuestion(
        question=question,
        hints=hints,
        grade_kind="practice_answer",
        expected_answer=expected_answer,
        answer_kind=answer_kind,
        expected_payload={"criteria": criteria},
        practice_context=practice_context,
    )


def _string_attr(attrs: dict[str, Any], name: str) -> str | None:
    value = attrs.get(name)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _number_attr(attrs: dict[str, Any], name: str) -> float | None:
    value = attrs.get(name)
    if isinstance(value, int | float):
        return float(value)
    return None


def _int_attr(attrs: dict[str, Any], name: str) -> int | None:
    value = attrs.get(name)
    if isinstance(value, int):
        return value
    return None


def _dict_attr(attrs: dict[str, Any], name: str) -> dict[str, Any] | None:
    value = attrs.get(name)
    if isinstance(value, dict):
        return value
    return None


def _list_attr(attrs: dict[str, Any], name: str) -> list[str]:
    value = attrs.get(name)
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _source_key(*, scope: str, index: int, component: str, attrs: dict[str, Any]) -> str:
    question = _string_attr(attrs, "question") or ""
    digest = hashlib.sha256(f"{scope}:{index}:{component}:{question}".encode()).hexdigest()
    return f"inline:{digest}"


def _remove_placeholder_question_id(content: str, placeholder: str) -> str:
    return content.replace(f' questionId="{placeholder}"', "")


def _int_value(value: Any) -> int | None:
    return value if isinstance(value, int) else None
