"""Pace offers for question-bank practice: ease (warm-ups) or stretch (harder), decided per concept.

Stateless by design: every trigger reads the learner's existing probe, attempt and
mastery rows. The client owns the session rules (one offer per concept per session,
dismissals), so nothing here is persisted. Copy names the concept, never the learner.
"""

import statistics
import uuid
from dataclasses import dataclass, field

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.courses.models import Concept, CourseConcept, LearningAttempt, LearningQuestion, ProbeEvent, UserConceptState
from src.courses.schemas import PaceSignal


_RECENT_WINDOW = 5
_EASE_MISS_STREAK = 3
_EASE_ACCURACY_MAX = 0.4
_EASE_SLOW_RATIO = 1.5
_STRETCH_MASTERY_MIN = 0.8
_STRETCH_RECENT_CORRECT_MIN = 4
_LEARNER_DURATION_WINDOW = 30


@dataclass(slots=True)
class _ConceptSignals:
    """Recent learner evidence on one concept, newest first."""

    mastery: float = 0.0
    recent_correct: list[bool] = field(default_factory=list)
    recent_duration_ms: list[int] = field(default_factory=list)
    recent_hints_used: list[int] = field(default_factory=list)
    learner_median_duration_ms: float | None = None


class PracticePaceService:
    """Decide whether to offer the learner a warm-up or a stretch on a concept."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def evaluate(
        self,
        *,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        concept_id: uuid.UUID,
        bank_exhausted: bool,
    ) -> PaceSignal | None:
        """Return an ease or stretch offer when its trigger fires, else None (steady)."""
        concept = await self._session.get(Concept, concept_id)
        if concept is None:
            return None
        signals = await self._load_signals(user_id=user_id, course_id=course_id, concept_id=concept_id)

        ease_reason = _ease_reason(signals)
        if ease_reason is not None:
            return PaceSignal(
                kind="ease",
                concept_id=concept_id,
                message=f"Want two quick warm-ups on {concept.name} before the next one?",
                reason=ease_reason,
            )
        if bank_exhausted and _stretch_ready(signals):
            return PaceSignal(
                kind="stretch",
                concept_id=concept_id,
                message=f"You've got {concept.name} down. Want one that pushes it further?",
                reason="high_mastery_bank_exhausted",
            )
        return None

    async def _load_signals(self, *, user_id: uuid.UUID, course_id: uuid.UUID, concept_id: uuid.UUID) -> _ConceptSignals:
        signals = _ConceptSignals()

        state = await self._session.scalar(
            select(UserConceptState).where(
                and_(UserConceptState.user_id == user_id, UserConceptState.concept_id == concept_id)
            )
        )
        if state is not None:
            signals.mastery = float(state.s_mastery)

        probe_rows = (
            await self._session.execute(
                select(ProbeEvent.correct, ProbeEvent.review_duration_ms)
                .where(and_(ProbeEvent.user_id == user_id, ProbeEvent.concept_id == concept_id))
                .order_by(ProbeEvent.ts.desc())
                .limit(_RECENT_WINDOW)
            )
        ).all()
        for correct, duration_ms in probe_rows:
            signals.recent_correct.append(bool(correct))
            if duration_ms is not None and duration_ms > 0:
                signals.recent_duration_ms.append(int(duration_ms))

        hint_rows = (
            await self._session.execute(
                select(LearningAttempt.hints_used)
                .join(LearningQuestion, LearningQuestion.id == LearningAttempt.question_id)
                .where(and_(LearningAttempt.user_id == user_id, LearningQuestion.concept_id == concept_id))
                .order_by(LearningAttempt.created_at.desc())
                .limit(_RECENT_WINDOW)
            )
        ).scalars().all()
        signals.recent_hints_used = [int(hints) for hints in hint_rows]

        course_durations = (
            await self._session.execute(
                select(ProbeEvent.review_duration_ms)
                .join(CourseConcept, CourseConcept.concept_id == ProbeEvent.concept_id)
                .where(
                    and_(
                        ProbeEvent.user_id == user_id,
                        CourseConcept.course_id == course_id,
                        ProbeEvent.review_duration_ms > 0,
                    )
                )
                .order_by(ProbeEvent.ts.desc())
                .limit(_LEARNER_DURATION_WINDOW)
            )
        ).scalars().all()
        durations = [int(value) for value in course_durations if value is not None]
        if durations:
            signals.learner_median_duration_ms = statistics.median(durations)

        return signals


def _ease_reason(signals: _ConceptSignals) -> str | None:
    recent = signals.recent_correct
    if len(recent) >= _EASE_MISS_STREAK and not any(recent[:_EASE_MISS_STREAK]):
        return "three_recent_misses"
    if len(recent) < _RECENT_WINDOW or signals.learner_median_duration_ms is None or not signals.recent_duration_ms:
        return None
    accuracy = sum(recent) / len(recent)
    concept_median = statistics.median(signals.recent_duration_ms)
    if accuracy < _EASE_ACCURACY_MAX and concept_median > _EASE_SLOW_RATIO * signals.learner_median_duration_ms:
        return "low_accuracy_and_slow"
    return None


def _stretch_ready(signals: _ConceptSignals) -> bool:
    recent = signals.recent_correct[:_RECENT_WINDOW]
    if signals.mastery < _STRETCH_MASTERY_MIN or len(recent) < _RECENT_WINDOW:
        return False
    if sum(recent) < _STRETCH_RECENT_CORRECT_MIN:
        return False
    return all(hints == 0 for hints in signals.recent_hints_used[:_RECENT_WINDOW])
