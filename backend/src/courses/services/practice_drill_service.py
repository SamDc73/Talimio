"""Adaptive practice drill generation service using batched direct LLM IRT."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, select

from src.ai.client import LLMClient
from src.config.settings import get_settings
from src.courses.models import Concept, CourseConcept, ProbeEvent, UserConceptState
from src.courses.schemas import PracticeDrillItem


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_MAX_GENERATION_ROUNDS = 5
_STRICT_SIGNATURE_ROUNDS = 2
_RECENT_PROBE_WINDOW = 20
_RECENT_PERFORMANCE_WINDOW = 20


@dataclass(slots=True)
class _LearnerProfile:
    """Minimal learner profile for prediction prompts."""

    mastery: float
    recent_correct: int
    recent_total: int
    learning_speed: float
    strengths: list[str]
    weaknesses: list[str]


class _QuestionPayload(BaseModel):
    """Single generated question payload from generation prompt."""

    question: str = Field(..., min_length=1)
    expected_answer: str = Field(..., min_length=1)

    model_config = ConfigDict(extra="forbid")


class _QuestionBatchPayload(BaseModel):
    """generation payload."""

    questions: list[_QuestionPayload] = Field(..., min_length=1)

    model_config = ConfigDict(extra="forbid")


class _PredictionBatchPayload(BaseModel):
    """batch prediction payload."""

    predicted_p_correct: list[float] = Field(..., min_length=1)

    model_config = ConfigDict(extra="forbid")


class PracticeDrillService:
    """Generate adaptive drill items using."""

    def __init__(self, session: AsyncSession, llm_client: LLMClient | None = None) -> None:
        self._session = session
        self._llm_client = llm_client or LLMClient()
        settings = get_settings()
        configured_core_model = (settings.PRIMARY_LLM_MODEL or "").strip()
        self._request_model: str | None = configured_core_model if configured_core_model else None
        self._core_model = configured_core_model if configured_core_model else "unknown-model"

    async def generate_drills(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
        concept_id: UUID,
        count: int,
    ) -> list[PracticeDrillItem]:
        """Generate adaptive drills for a course concept."""
        if count <= 0:
            message = "count must be > 0"
            raise ValueError(message)

        concept = await self._resolve_course_concept(course_id=course_id, concept_id=concept_id)
        if concept is None:
            message = "Concept is not assigned to this course"
            raise LookupError(message)

        learner = await self._load_learner_profile(user_id=user_id, concept_id=concept_id)
        seen_questions, seen_signatures = await self._load_recent_seen_keys(user_id=user_id, concept_id=concept_id)

        lesson_id = uuid5(NAMESPACE_URL, f"concept-lesson:{course_id}:{concept_id}")
        drills: list[PracticeDrillItem] = []
        rounds = 0

        while len(drills) < count and rounds < _MAX_GENERATION_ROUNDS:
            rounds += 1
            remaining = count - len(drills)
            enforce_signature_uniqueness = rounds <= _STRICT_SIGNATURE_ROUNDS
            history_block = self._build_history_block(seen_signatures)
            question_batch = await self._generate_question_batch(
                concept=concept,
                history=history_block,
                count=remaining,
                user_id=user_id,
            )
            predicted_batch = await self._predict_p_correct_batch(
                questions=[item.question for item in question_batch],
                learner=learner,
                concept_name=concept.name,
                user_id=user_id,
            )

            for generated, predicted in zip(question_batch, predicted_batch, strict=False):
                question = generated.question.strip()
                expected = generated.expected_answer.strip()
                if not question or not expected:
                    continue

                question_key = self._normalize_question_key(question)
                signature = self._derive_structure_signature(question)

                if question_key in seen_questions:
                    continue
                if enforce_signature_uniqueness and signature in seen_signatures:
                    continue

                seen_questions.add(question_key)
                seen_signatures.add(signature)

                drills.append(
                    PracticeDrillItem(
                        concept_id=concept_id,
                        lesson_id=lesson_id,
                        question=question,
                        expected_latex=expected,
                        hints=[],
                        structure_signature=signature,
                        predicted_p_correct=self._clamp_probability(predicted),
                        core_model=self._core_model,
                    )
                )
                if len(drills) >= count:
                    break

        if len(drills) < count:
            message = f"Unable to generate {count} unique practice drills right now. Please try again."
            raise ValueError(message)

        return drills

    async def _resolve_course_concept(self, *, course_id: UUID, concept_id: UUID) -> Concept | None:
        return await self._session.scalar(
            select(Concept)
            .join(CourseConcept, CourseConcept.concept_id == Concept.id)
            .where(
                and_(
                    CourseConcept.course_id == course_id,
                    CourseConcept.concept_id == concept_id,
                )
            )
        )

    async def _load_learner_profile(self, *, user_id: UUID, concept_id: UUID) -> _LearnerProfile:
        state = await self._session.scalar(
            select(UserConceptState).where(
                and_(
                    UserConceptState.user_id == user_id,
                    UserConceptState.concept_id == concept_id,
                )
            )
        )

        outcomes = (
            (
                await self._session.execute(
                    select(ProbeEvent.correct)
                    .where(
                        and_(
                            ProbeEvent.user_id == user_id,
                            ProbeEvent.concept_id == concept_id,
                        )
                    )
                    .order_by(ProbeEvent.ts.desc())
                    .limit(_RECENT_PERFORMANCE_WINDOW)
                )
            )
            .scalars()
            .all()
        )

        recent_total = len(outcomes)
        recent_correct = sum(1 for item in outcomes if item)
        mastery = float(state.s_mastery) if state is not None else 0.5

        learning_speed = 1.0
        if state is not None and isinstance(state.learner_profile, dict):
            speed_raw = state.learner_profile.get("learning_speed")
            if isinstance(speed_raw, (int, float)):
                learning_speed = float(speed_raw)

        return _LearnerProfile(
            mastery=mastery,
            recent_correct=recent_correct,
            recent_total=recent_total,
            learning_speed=learning_speed,
            strengths=[],
            weaknesses=[],
        )

    async def _load_recent_seen_keys(self, *, user_id: UUID, concept_id: UUID) -> tuple[set[str], set[str]]:
        rows = (
            (
                await self._session.execute(
                    select(ProbeEvent.extra)
                    .where(
                        and_(
                            ProbeEvent.user_id == user_id,
                            ProbeEvent.concept_id == concept_id,
                        )
                    )
                    .order_by(ProbeEvent.ts.desc())
                    .limit(_RECENT_PROBE_WINDOW)
                )
            )
            .scalars()
            .all()
        )

        questions: set[str] = set()
        signatures: set[str] = set()
        for extra in rows:
            if not isinstance(extra, dict):
                continue

            question_raw = extra.get("question")
            if isinstance(question_raw, str) and question_raw.strip():
                questions.add(self._normalize_question_key(question_raw))

            signature_raw = extra.get("structure_signature")
            if isinstance(signature_raw, str) and signature_raw.strip():
                signatures.add(signature_raw.strip().lower())

        return questions, signatures

    async def _generate_question_batch(
        self,
        *,
        concept: Concept,
        history: str,
        count: int,
        user_id: UUID,
    ) -> list[_QuestionPayload]:
        payload = await self._llm_client.generate_practice_question_batch(
            concept=concept.name,
            concept_description=concept.description,
            history=history,
            count=count,
            response_model=_QuestionBatchPayload,
            user_id=user_id,
            model=self._request_model,
        )
        if not isinstance(payload, _QuestionBatchPayload):
            message = "Unexpected generation payload"
            raise TypeError(message)
        return payload.questions

    async def _predict_p_correct_batch(
        self,
        *,
        questions: list[str],
        learner: _LearnerProfile,
        concept_name: str,
        user_id: UUID,
    ) -> list[float]:
        if not questions:
            return []

        prediction_example = ", ".join(["0.70"] * len(questions))
        payload = await self._llm_client.predict_practice_correctness_batch(
            concept=concept_name,
            mastery=learner.mastery,
            recent_correct=learner.recent_correct,
            recent_total=learner.recent_total,
            learning_speed=learner.learning_speed,
            strengths=learner.strengths,
            weaknesses=learner.weaknesses,
            questions=questions,
            predictions_example=prediction_example,
            response_model=_PredictionBatchPayload,
            user_id=user_id,
            model=self._request_model,
        )
        if not isinstance(payload, _PredictionBatchPayload):
            message = "Unexpected prediction payload"
            raise TypeError(message)

        predictions = [self._clamp_probability(value) for value in payload.predicted_p_correct]
        if len(predictions) != len(questions):
            message = "predicted_p_correct size mismatch"
            raise ValueError(message)

        return predictions

    def _build_history_block(self, signatures: set[str]) -> str:
        if not signatures:
            return "- none"

        ordered = sorted(signatures)
        selected = ordered[:20]
        return "\n".join(f"- {item}" for item in selected)

    @staticmethod
    def _normalize_question_key(question: str) -> str:
        base = question.strip().lower()
        collapsed = re.sub(r"\s+", " ", base)
        return re.sub(r"\d+", "n", collapsed)

    @staticmethod
    def _derive_structure_signature(question: str) -> str:
        normalized = PracticeDrillService._normalize_question_key(question)
        tokens = re.findall(r"[a-z]+|n", normalized)
        if not tokens:
            return "question.unknown"
        return ".".join(tokens[:6])

    @staticmethod
    def _clamp_probability(value: float) -> float:
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return float(value)
