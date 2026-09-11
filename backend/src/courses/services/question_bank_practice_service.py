"""Serve an instructor's question bank to one learner.

Picks bank questions for a concept (unseen first, then missed, never a repeat
within the session), materializes the learner's grading row in
``learning_questions`` with ``source_key = "bank:<id>"``, and answers the two
questions the pace engine needs: does the concept have bank questions at all,
and has this learner already cleared them.
"""

import random
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.courses.models import CourseQuestion, LearningAttempt, LearningQuestion
from src.courses.schemas import ProbeFamily, ProbeRendererKind, QuestionSetPracticeContext


QUESTION_BANK_SOURCE_COMPONENT = "question_bank"
QUESTION_BANK_CORE_MODEL = "question_bank"


def bank_source_key(course_question_id: uuid.UUID) -> str:
    """Idempotency key for the per-learner row materialized from one bank question."""
    return f"bank:{course_question_id}"


def bank_probe_family(answer_kind: str) -> ProbeFamily:
    """Bank questions are either a recognition choice or a direct recall answer."""
    return "recognition_discrimination" if answer_kind == "choice" else "free_recall"


def bank_renderer_kind(answer_kind: str) -> ProbeRendererKind:
    """Return the renderer contract matching :func:`bank_probe_family`."""
    return "multiple_choice" if answer_kind == "choice" else "free_form"


@dataclass(slots=True)
class AttemptHistory:
    """Attempt record of one learner on one bank question."""

    attempts: int = 0
    correct_attempts: int = 0
    last_correct: bool | None = None

    def pick_tier(self) -> int:
        """Unseen questions come first, then ones the learner last missed, then ones already correct."""
        if self.attempts == 0:
            return 0
        if self.last_correct is False:
            return 1
        return 2


class QuestionBankPracticeService:
    """Pick, materialize and inspect bank questions for one learner."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def pick_questions(
        self,
        *,
        course_id: uuid.UUID,
        user_id: uuid.UUID,
        concept_id: uuid.UUID,
        count: int,
        exclude_question_ids: Sequence[uuid.UUID],
    ) -> list[CourseQuestion]:
        """Choose bank questions for one concept: unseen first, then missed, then correct; never one served this session."""
        result = await self._session.execute(
            select(CourseQuestion).where(
                CourseQuestion.course_id == course_id,
                CourseQuestion.concept_id == concept_id,
            )
        )
        candidates = list(result.scalars().all())
        if not candidates:
            return []

        excluded_source_keys = await self._source_keys_for_learning_question_ids(
            course_id=course_id,
            user_id=user_id,
            learning_question_ids=exclude_question_ids,
        )
        history_by_source_key = await self.attempt_history_by_source_key(course_id=course_id, user_id=user_id)

        random.SystemRandom().shuffle(candidates)
        ranked = sorted(
            (item for item in candidates if bank_source_key(item.id) not in excluded_source_keys),
            key=lambda item: history_by_source_key.get(bank_source_key(item.id), AttemptHistory()).pick_tier(),
        )
        return ranked[:count]

    async def concept_has_questions(self, *, course_id: uuid.UUID, concept_id: uuid.UUID) -> bool:
        """Return False for coverage gaps: concepts the graph implies but the instructor wrote nothing for."""
        first_id = await self._session.scalar(
            select(CourseQuestion.id)
            .where(CourseQuestion.course_id == course_id, CourseQuestion.concept_id == concept_id)
            .limit(1)
        )
        return first_id is not None

    async def concept_bank_exhausted(self, *, course_id: uuid.UUID, user_id: uuid.UUID, concept_id: uuid.UUID) -> bool:
        """Return True when every bank question for the concept was correct on this learner's latest attempt."""
        question_ids = (
            await self._session.execute(
                select(CourseQuestion.id).where(
                    CourseQuestion.course_id == course_id,
                    CourseQuestion.concept_id == concept_id,
                )
            )
        ).scalars().all()
        if not question_ids:
            return False
        history = await self.attempt_history_by_source_key(course_id=course_id, user_id=user_id)
        return all(
            history.get(bank_source_key(question_id), AttemptHistory()).last_correct is True
            for question_id in question_ids
        )

    async def materialize_learning_question(
        self,
        *,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        bank_question: CourseQuestion,
        practice_context: QuestionSetPracticeContext,
    ) -> LearningQuestion:
        """Return this learner's grading row for a bank question, creating it on first use."""
        if bank_question.concept_id is None:
            message = "Bank question is not mapped to a concept yet"
            raise ValueError(message)

        source_key = bank_source_key(bank_question.id)
        existing = await self._session.scalar(
            select(LearningQuestion).where(
                LearningQuestion.user_id == user_id,
                LearningQuestion.course_id == course_id,
                LearningQuestion.source_component == QUESTION_BANK_SOURCE_COMPONENT,
                LearningQuestion.source_key == source_key,
            )
        )
        if existing is not None:
            return existing

        question = LearningQuestion(
            user_id=user_id,
            course_id=course_id,
            concept_id=bank_question.concept_id,
            lesson_id=None,
            question=bank_question.question,
            expected_answer=bank_question.expected_answer,
            answer_kind=bank_question.answer_kind,
            grade_kind="practice_answer",
            expected_payload={},
            question_payload={
                "answerKind": bank_question.answer_kind,
                "probeFamily": bank_probe_family(bank_question.answer_kind),
                "rendererKind": bank_renderer_kind(bank_question.answer_kind),
                "choices": bank_question.choices,
                "hints": bank_question.hints,
            },
            hints=bank_question.hints,
            structure_signature=source_key,
            predicted_p_correct=0.5,
            target_probability=0.5,
            target_low=0.0,
            target_high=1.0,
            core_model=QUESTION_BANK_CORE_MODEL,
            practice_context=practice_context,
            source_component=QUESTION_BANK_SOURCE_COMPONENT,
            source_key=source_key,
        )
        self._session.add(question)
        await self._session.flush()
        return question

    async def _source_keys_for_learning_question_ids(
        self,
        *,
        course_id: uuid.UUID,
        user_id: uuid.UUID,
        learning_question_ids: Sequence[uuid.UUID],
    ) -> set[str]:
        if not learning_question_ids:
            return set()
        rows = await self._session.execute(
            select(LearningQuestion.source_key).where(
                LearningQuestion.id.in_(list(learning_question_ids)),
                LearningQuestion.user_id == user_id,
                LearningQuestion.course_id == course_id,
                LearningQuestion.source_component == QUESTION_BANK_SOURCE_COMPONENT,
            )
        )
        return {source_key for source_key in rows.scalars().all() if source_key}

    async def attempt_history_by_source_key(
        self, *, course_id: uuid.UUID, user_id: uuid.UUID
    ) -> dict[str, AttemptHistory]:
        """Return this learner's attempt record per bank question, keyed by source key."""
        rows = await self._session.execute(
            select(LearningQuestion.source_key, LearningAttempt.is_correct)
            .join(LearningAttempt, LearningAttempt.question_id == LearningQuestion.id)
            .where(
                and_(
                    LearningQuestion.course_id == course_id,
                    LearningQuestion.user_id == user_id,
                    LearningQuestion.source_component == QUESTION_BANK_SOURCE_COMPONENT,
                )
            )
            .order_by(LearningAttempt.created_at.desc())
        )
        history: dict[str, AttemptHistory] = {}
        for source_key, is_correct in rows.all():
            if not source_key:
                continue
            entry = history.setdefault(source_key, AttemptHistory())
            if entry.attempts == 0:
                entry.last_correct = bool(is_correct)
            entry.attempts += 1
            if is_correct:
                entry.correct_attempts += 1
        return history
