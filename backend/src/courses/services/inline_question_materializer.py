"""Materialize server-owned learning questions from generated lessons."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

from pydantic import JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.models import GeneratedInlineQuestion, GeneratedLesson
from src.courses.models import LearningQuestion


@dataclass(frozen=True)
class _InlineQuestion:
    question: str
    hints: list[str]
    grade_kind: str
    expected_answer: str | None
    answer_kind: str | None
    expected_payload: dict[str, JsonValue]
    practice_context: str


class InlineQuestionMaterializer:
    """Create hidden learning-question rows and replace placeholders with question IDs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def materialize_generated_lesson(
        self,
        *,
        generated: GeneratedLesson,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
        concept_id: uuid.UUID | None,
        lesson_version_id: uuid.UUID | None,
    ) -> str:
        """Persist inline questions and return the content with placeholders replaced by question IDs."""
        content = generated.content
        for index, inline in enumerate(generated.inline_questions):
            question_id = await self._upsert_question(
                user_id=user_id,
                course_id=course_id,
                lesson_id=lesson_id,
                concept_id=concept_id,
                lesson_version_id=lesson_version_id,
                source_component=inline.component,
                source_key=_source_key(
                    scope="content",
                    index=index,
                    component=inline.component,
                    question=inline.question,
                ),
                inline_question=_inline_question_from_generated(inline),
            )
            content = content.replace(inline.placeholder, str(question_id))
        return content

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
            object.__setattr__(existing, "question_payload", question_payload)  # noqa: PLC2801
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


def _inline_question_from_generated(inline: GeneratedInlineQuestion) -> _InlineQuestion:
    return _InlineQuestion(
        question=inline.question,
        hints=inline.hints,
        grade_kind=inline.grade_kind,
        expected_answer=inline.expected_answer,
        answer_kind=inline.answer_kind,
        expected_payload=inline.expected_payload,
        practice_context=inline.practice_context,
    )


def _source_key(*, scope: str, index: int, component: str, question: str) -> str:
    digest = hashlib.sha256(f"{scope}:{index}:{component}:{question}".encode()).hexdigest()
    return f"inline:{digest}"
