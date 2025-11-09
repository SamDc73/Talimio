"""User concept state management for adaptive scheduling."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import and_, select

from src.config.settings import get_settings
from src.courses.models import ProbeEvent, UserConceptState


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)

settings = get_settings()


class ConceptStateService:
    """Manage learner concept mastery state and probe logging."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_user_concept_state(
        self,
        *,
        user_id: UUID,
        concept_id: UUID,
        create: bool = True,
    ) -> UserConceptState | None:
        """Fetch or lazily create the concept state for a learner."""
        state = await self._session.scalar(
            select(UserConceptState).where(
                and_(
                    UserConceptState.user_id == user_id,
                    UserConceptState.concept_id == concept_id,
                )
            )
        )
        if state is not None or not create:
            return state

        state = UserConceptState(user_id=user_id, concept_id=concept_id)
        self._session.add(state)
        await self._session.flush()
        return state

    async def update_mastery(
        self,
        *,
        user_id: UUID,
        concept_id: UUID,
        correct: bool,
        latency_ms: int | None = None,
    ) -> UserConceptState:
        """Update mastery score following an interaction."""
        state = await self.get_user_concept_state(user_id=user_id, concept_id=concept_id)
        if state is None:
            msg = "Concept state could not be instantiated"
            raise RuntimeError(msg)
        previous_mastery = state.s_mastery
        delta = settings.LEARNING_DELTA_CORRECT if correct else settings.LEARNING_DELTA_INCORRECT
        if latency_ms is not None and latency_ms > 0:
            latency_penalty = min(latency_ms / settings.LATENCY_PENALTY_MULTIPLIER, settings.LATENCY_PENALTY_MAX)
            delta -= latency_penalty

        updated_mastery = max(0.0, min(1.0, previous_mastery + delta))
        state.s_mastery = updated_mastery
        state.exposures += 1
        state.last_seen_at = datetime.now(UTC)
        await self._session.flush()
        return state

    async def log_probe_event(
        self,
        *,
        user_id: UUID,
        concept_id: UUID,
        rating: int,
        review_duration_ms: int,
        correct: bool,
        latency_ms: int | None = None,
        context_tag: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ProbeEvent:
        """Record a probe event for analytics and future scheduling."""
        event = ProbeEvent(
            user_id=user_id,
            concept_id=concept_id,
            ts=datetime.now(UTC),
            correct=correct,
            latency_ms=latency_ms,
            rating=rating,
            review_duration_ms=review_duration_ms,
            context_tag=context_tag,
            extra=extra or {},
        )
        self._session.add(event)
        await self._session.flush()
        return event

