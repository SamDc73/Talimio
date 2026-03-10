"""Adaptive practice drill generation service using batched direct LLM IRT."""

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.client import LLMClient
from src.config.schema_casing import build_camel_config
from src.config.settings import get_settings
from src.courses.models import Concept, CourseConcept, ProbeEvent, UserConceptState
from src.courses.schemas import PracticeDrillItem


_RECENT_PROBE_WINDOW = 20
_RECENT_PERFORMANCE_WINDOW = 20
_TARGET_PROBABILITY_HIGH_MASTERY = 0.52
_TARGET_PROBABILITY_MID_MASTERY = 0.62
_TARGET_PROBABILITY_LOW_MASTERY = 0.70


@dataclass(slots=True)
class _LearnerProfile:
    """Learner profile for practice generation and prediction prompts."""

    mastery: float
    recent_correct: int
    recent_total: int
    learning_speed: float
    retention_rate: float
    success_rate: float
    overdue: bool
    struggling_concepts: list[str]


@dataclass(slots=True)
class _GenerationContext:
    """Derived generation controls for one request."""

    learner_context: str
    difficulty_guidance: str
    review_status: str
    target_probability: float
    target_low: float
    target_high: float


class _QuestionPayload(BaseModel):
    """Single generated question payload from generation prompt."""

    question: str = Field(..., min_length=1)
    expected_answer: str = Field(..., min_length=1)
    answer_kind: Literal["math_latex", "text"] = Field(...)

    model_config = build_camel_config(extra="forbid")


class _QuestionBatchPayload(BaseModel):
    """generation payload."""

    questions: list[_QuestionPayload] = Field(..., min_length=1)

    model_config = build_camel_config(extra="forbid")


class _PredictionBatchPayload(BaseModel):
    """batch prediction payload."""

    predicted_p_correct: list[Annotated[float, Field(ge=0.0, le=1.0)]] = Field(..., min_length=1)

    model_config = ConfigDict(extra="forbid")


class PracticeDrillService:
    """Generate adaptive drill items using."""

    def __init__(self, session: AsyncSession, llm_client: LLMClient | None = None) -> None:
        self._session = session
        self._llm_client = llm_client or LLMClient()
        self._core_model = get_settings().primary_llm_model

    async def generate_drills(
        self,
        *,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        concept_id: uuid.UUID,
        count: int,
    ) -> list[PracticeDrillItem]:
        """Generate adaptive drills for a course concept."""
        concept = await self._resolve_course_concept(course_id=course_id, concept_id=concept_id)
        if concept is None:
            message = "Concept is not assigned to this course"
            raise LookupError(message)

        learner = await self._load_learner_profile(user_id=user_id, course_id=course_id, concept_id=concept_id)
        generation_context = self._build_generation_context(learner)
        seen_questions, seen_signatures = await self._load_recent_seen_keys(user_id=user_id, concept_id=concept_id)

        lesson_id = uuid.uuid5(uuid.NAMESPACE_URL, f"concept-lesson:{course_id}:{concept_id}")
        drills = await self._generate_drills_once(
            concept=concept,
            concept_id=concept_id,
            lesson_id=lesson_id,
            learner=learner,
            generation_context=generation_context,
            seen_questions=seen_questions,
            seen_signatures=seen_signatures,
            user_id=user_id,
            count=count,
        )

        if len(drills) < count:
            message = f"Unable to generate {count} unique practice drills right now. Please try again."
            raise ValueError(message)

        return drills

    async def _resolve_course_concept(self, *, course_id: uuid.UUID, concept_id: uuid.UUID) -> Concept | None:
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

    def _build_generation_context(self, learner: _LearnerProfile) -> _GenerationContext:
        target_probability, target_low, target_high = self._build_target_band(
            mastery=learner.mastery,
            recent_correct=learner.recent_correct,
            recent_total=learner.recent_total,
        )
        return _GenerationContext(
            learner_context=self._build_learner_context(learner),
            difficulty_guidance=self._build_difficulty_guidance(learner.mastery, learner.overdue),
            review_status=self._build_review_status(learner.overdue),
            target_probability=target_probability,
            target_low=target_low,
            target_high=target_high,
        )

    async def _generate_drills_once(
        self,
        *,
        concept: Concept,
        concept_id: uuid.UUID,
        lesson_id: uuid.UUID,
        learner: _LearnerProfile,
        generation_context: _GenerationContext,
        seen_questions: set[str],
        seen_signatures: set[str],
        user_id: uuid.UUID,
        count: int,
    ) -> list[PracticeDrillItem]:
        candidate_count = max(count * 2, count + 3)
        question_batch = await self._generate_question_batch(
            concept=concept,
            history=self._build_history_block(seen_signatures),
            learner_context=generation_context.learner_context,
            difficulty_guidance=generation_context.difficulty_guidance,
            count=candidate_count,
            user_id=user_id,
        )
        predicted_batch = await self._predict_p_correct_batch(
            questions=[item.question for item in question_batch],
            learner=learner,
            concept_name=concept.name,
            review_status=generation_context.review_status,
            user_id=user_id,
        )

        ranked_candidates = sorted(
            ((generated, predicted) for generated, predicted in zip(question_batch, predicted_batch, strict=True)),
            key=lambda item: self._difficulty_rank(
                probability=item[1],
                target=generation_context.target_probability,
                target_low=generation_context.target_low,
                target_high=generation_context.target_high,
            ),
        )

        selected_drills: list[PracticeDrillItem] = []
        for generated, predicted_value in ranked_candidates:
            question = generated.question.strip()
            expected = generated.expected_answer.strip()
            answer_kind = generated.answer_kind
            if not question or not expected:
                continue

            question_key = self._normalize_question_key(question)
            signature = self._derive_structure_signature(question)

            if question_key in seen_questions:
                continue
            if signature in seen_signatures:
                continue

            seen_questions.add(question_key)
            seen_signatures.add(signature)
            selected_drills.append(
                PracticeDrillItem(
                    concept_id=concept_id,
                    lesson_id=lesson_id,
                    question=question,
                    expected_answer=expected,
                    answer_kind=answer_kind,
                    hints=[],
                    structure_signature=signature,
                    predicted_p_correct=predicted_value,
                    target_probability=generation_context.target_probability,
                    target_low=generation_context.target_low,
                    target_high=generation_context.target_high,
                    core_model=self._core_model,
                )
            )
            if len(selected_drills) >= count:
                break

        return selected_drills

    async def _load_learner_profile(
        self, *, user_id: uuid.UUID, course_id: uuid.UUID, concept_id: uuid.UUID
    ) -> _LearnerProfile:
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
        retention_rate = 0.8
        success_rate = 0.5
        if state is not None and isinstance(state.learner_profile, dict):
            speed_raw = state.learner_profile.get("learning_speed")
            if isinstance(speed_raw, (int, float)):
                learning_speed = float(speed_raw)
            retention_raw = state.learner_profile.get("retention_rate")
            if isinstance(retention_raw, (int, float)):
                retention_rate = float(retention_raw)
            success_raw = state.learner_profile.get("success_rate")
            if isinstance(success_raw, (int, float)):
                success_rate = float(success_raw)

        overdue = False
        if state is not None and state.next_review_at is not None:
            next_review_at = state.next_review_at
            if next_review_at.tzinfo is None:
                next_review_at = next_review_at.replace(tzinfo=UTC)
            overdue = next_review_at < datetime.now(UTC)

        struggling_rows = (
            (
                await self._session.execute(
                    select(Concept.name)
                    .join(CourseConcept, CourseConcept.concept_id == Concept.id)
                    .join(
                        UserConceptState,
                        and_(
                            UserConceptState.concept_id == Concept.id,
                            UserConceptState.user_id == user_id,
                        ),
                    )
                    .where(
                        CourseConcept.course_id == course_id,
                        UserConceptState.s_mastery <= 0.3,
                    )
                    .order_by(Concept.name.asc())
                )
            )
            .scalars()
            .all()
        )
        struggling_concepts = list(
            dict.fromkeys(name.strip() for name in struggling_rows if isinstance(name, str) and name.strip())
        )

        return _LearnerProfile(
            mastery=mastery,
            recent_correct=recent_correct,
            recent_total=recent_total,
            learning_speed=learning_speed,
            retention_rate=retention_rate,
            success_rate=success_rate,
            overdue=overdue,
            struggling_concepts=struggling_concepts,
        )

    async def _load_recent_seen_keys(self, *, user_id: uuid.UUID, concept_id: uuid.UUID) -> tuple[set[str], set[str]]:
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
        learner_context: str,
        difficulty_guidance: str,
        count: int,
        user_id: uuid.UUID,
    ) -> list[_QuestionPayload]:
        payload = await self._llm_client.generate_practice_question_batch(
            concept=concept.name,
            concept_description=concept.description,
            history=history,
            learner_context=learner_context,
            difficulty_guidance=difficulty_guidance,
            count=count,
            response_model=_QuestionBatchPayload,
            user_id=user_id,
        )
        return payload.questions

    async def _predict_p_correct_batch(
        self,
        *,
        questions: list[str],
        learner: _LearnerProfile,
        concept_name: str,
        review_status: str,
        user_id: uuid.UUID,
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
            retention_rate=learner.retention_rate,
            success_rate=learner.success_rate,
            struggling_concepts=learner.struggling_concepts,
            review_status=review_status,
            questions=questions,
            predictions_example=prediction_example,
            response_model=_PredictionBatchPayload,
            user_id=user_id,
        )
        predictions = payload.predicted_p_correct
        if len(predictions) != len(questions):
            message = "predicted_p_correct size mismatch"
            raise RuntimeError(message)

        return predictions

    def _build_history_block(self, signatures: set[str]) -> str:
        if not signatures:
            return "- none"

        ordered = sorted(signatures)
        selected = ordered[:20]
        return "\n".join(f"- {item}" for item in selected)

    @staticmethod
    def _mastery_label(mastery: float) -> str:
        if mastery >= 0.7:
            return "high"
        if mastery >= 0.3:
            return "mid"
        return "low"

    def _build_learner_context(self, learner: _LearnerProfile) -> str:
        lines = [
            f"Mastery: {learner.mastery:.2f} ({self._mastery_label(learner.mastery)})",
            f"Recent performance: {learner.recent_correct}/{learner.recent_total} correct recently",
            f"Learning speed: {learner.learning_speed:.1f}x",
            f"Retention rate: {learner.retention_rate:.2f}",
            f"Success rate: {learner.success_rate:.2f}",
            f"Review status: {self._build_review_status(learner.overdue)}",
        ]
        if learner.struggling_concepts:
            lines.append(f"Course-wide struggling concepts: {', '.join(learner.struggling_concepts)}")
        else:
            lines.append("Course-wide struggling concepts: none")
        return "\n".join(lines)

    @staticmethod
    def _build_review_status(overdue: bool) -> str:
        if overdue:
            return "OVERDUE"
        return "on schedule"

    @staticmethod
    def _build_difficulty_guidance(mastery: float, overdue: bool) -> str:
        if mastery >= 0.7:
            guidance = "Push toward edge cases, multi-step problems, and subtle traps. The learner is solid on basics."
        elif mastery >= 0.3:
            guidance = (
                "Balance reinforcement with moderate challenge. "
                "Include one straightforward and one stretch question per batch."
            )
        else:
            guidance = (
                "Start with foundational questions. Build confidence before complexity. "
                "Use concrete values and simple structure."
            )

        if overdue:
            return (
                "Begin with a retrieval-style question that tests recall of the core idea "
                "before introducing new variations. "
                f"{guidance}"
            )
        return guidance

    def _build_target_band(self, *, mastery: float, recent_correct: int, recent_total: int) -> tuple[float, float, float]:
        if mastery >= 0.7:
            target = _TARGET_PROBABILITY_HIGH_MASTERY
            band_width = 0.08
        elif mastery >= 0.3:
            target = _TARGET_PROBABILITY_MID_MASTERY
            band_width = 0.1
        else:
            target = _TARGET_PROBABILITY_LOW_MASTERY
            band_width = 0.12

        if recent_total > 0:
            recent_accuracy = recent_correct / recent_total
            if recent_total >= 3 and recent_accuracy < 0.5:
                target -= 0.04

        target_low = max(0.0, target - band_width)
        target_high = min(1.0, target + band_width)
        return target, target_low, target_high

    @staticmethod
    def _difficulty_rank(*, probability: float, target: float, target_low: float, target_high: float) -> tuple[float, float]:
        if probability < target_low:
            distance_to_band = target_low - probability
        elif probability > target_high:
            distance_to_band = probability - target_high
        else:
            distance_to_band = 0.0
        return distance_to_band, abs(probability - target)

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
