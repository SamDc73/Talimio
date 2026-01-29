"""LECTOR scheduling service implementing semantic-aware spaced repetition.

Embedding-based confusors are computed and persisted at course creation (or
immediately after backfilling embeddings). The scheduler reads ConceptSimilarity
and does not compute on-the-fly fallback from embeddings.
"""

import logging
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import TypedDict
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import get_settings
from src.courses.models import (
    _DEFAULT_LEARNER_PROFILE,
    Concept,
    ConceptSimilarity,
    CourseConcept,
    ProbeEvent,
    UserConceptState,
)

from .concept_graph_service import FrontierEntry


logger = logging.getLogger(__name__)


LEARNER_PROFILE_EMA = 0.1
LEARNER_PROFILE_SPEED_MIN = 0.3
LEARNER_PROFILE_SPEED_MAX = 2.0
LEARNER_PROFILE_SPEED_BASE_MS = 60000
LEARNER_PROFILE_SPEED_FLOOR_MS = 500
LEARNER_PROFILE_SENSITIVITY_DECAY = 0.9
LEARNER_PROFILE_SENSITIVITY_BOOST = 1.1
LEARNER_PROFILE_SENSITIVITY_MIN = 0.4
LEARNER_PROFILE_SENSITIVITY_MAX = 1.6


class DueConceptEntry(TypedDict):
    """Typed structure representing a due concept entry."""

    concept: Concept
    state: UserConceptState


class LectorSchedulerService:
    """Service implementing LECTOR review interval calculations and caching."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()
        self._unlock_threshold = float(self._settings.ADAPTIVE_UNLOCK_MASTERY_THRESHOLD)
        self._confusion_lambda = float(self._settings.ADAPTIVE_CONFUSION_LAMBDA)
        self._risk_recent_k = int(self._settings.ADAPTIVE_RISK_RECENT_K)

    async def rank_frontier_entries(
        self,
        *,
        user_id: UUID,
        entries: Sequence[FrontierEntry],
        due_entries: Sequence[DueConceptEntry],
    ) -> list[FrontierEntry]:
        """Reorder frontier entries using mastery and semantic interference penalties."""
        entry_list = list(entries)
        if not entry_list:
            return []

        recent_ids = await self._recent_concept_ids(user_id)
        due_ids = {item["concept"].id for item in due_entries}
        context_ids = set(recent_ids) | due_ids

        unlocked: list[FrontierEntry] = []
        locked: list[FrontierEntry] = []

        for entry in entry_list:
            if entry["unlocked"]:
                unlocked.append(entry)
            else:
                locked.append(entry)

        unlocked_concept_ids = {entry["concept"].id for entry in unlocked}
        sigma_map = await self._sigma_for_concepts(unlocked_concept_ids, context_ids)

        unlocked.sort(
            key=lambda entry: self._frontier_sort_key(
                entry,
                sigma_map.get(entry["concept"].id, 0.0),
            )
        )
        return unlocked + locked

    def _frontier_sort_key(self, entry: FrontierEntry, sigma_value: float) -> tuple[float, str]:
        """Sort key prioritizing low mastery while penalizing high semantic risk (LECTOR §3.1)."""
        concept = entry["concept"]
        identifier = (concept.name or "").strip().lower() or (concept.slug or "").strip().lower()
        mastery = self._mastery_value(entry["state"])
        sensitivity = self._semantic_sensitivity(entry["state"])
        priority = (1.0 - mastery) - (self._confusion_lambda * sensitivity * sigma_value)
        return (-priority, identifier)

    def _mastery_value(self, state: UserConceptState | None) -> float:
        """Extract mastery value from user concept state."""
        if state is None or state.s_mastery is None:
            return 0.0
        return float(state.s_mastery)

    def _semantic_sensitivity(self, state: UserConceptState | None) -> float:
        """Return learner-specific sensitivity coefficient."""
        baseline = float(_DEFAULT_LEARNER_PROFILE["semantic_sensitivity"])
        if state is None or not state.learner_profile:
            return baseline
        candidate = state.learner_profile.get("semantic_sensitivity", baseline)
        try:
            return float(candidate)
        except (TypeError, ValueError):
            return baseline

    @staticmethod
    def _coerce_uuid(value: object) -> UUID:
        """Normalize database-returned identifiers to UUID instances."""
        if isinstance(value, UUID):
            return value
        try:
            return UUID(str(value))
        except (TypeError, ValueError) as exc:
            message = f"Expected UUID-compatible value, got {value!r}"
            raise ValueError(message) from exc

    async def _recent_concept_ids(self, user_id: UUID) -> list[UUID]:
        if self._risk_recent_k <= 0:
            return []
        rows = await self._session.execute(
            select(ProbeEvent.concept_id)
            .where(ProbeEvent.user_id == user_id)
            .order_by(ProbeEvent.ts.desc())
            .limit(self._risk_recent_k)
        )
        concepts = []
        seen: set[UUID] = set()
        for concept_id in rows.scalars():
            if concept_id not in seen:
                seen.add(concept_id)
                concepts.append(concept_id)
        return concepts

    async def _sigma_for_concepts(
        self,
        concept_ids: set[UUID],
        context_ids: set[UUID],
    ) -> dict[UUID, float]:
        if not concept_ids or not context_ids:
            return dict.fromkeys(concept_ids, 0.0)

        concept_list = list(concept_ids)
        context_list = list(context_ids)

        result = await self._session.execute(
            select(
                ConceptSimilarity.concept_a_id,
                ConceptSimilarity.concept_b_id,
                ConceptSimilarity.similarity,
            ).where(
                or_(
                    and_(
                        ConceptSimilarity.concept_a_id.in_(concept_list),
                        ConceptSimilarity.concept_b_id.in_(context_list),
                    ),
                    and_(
                        ConceptSimilarity.concept_b_id.in_(concept_list),
                        ConceptSimilarity.concept_a_id.in_(context_list),
                    ),
                )
            )
        )

        sigma_map: dict[UUID, float] = dict.fromkeys(concept_ids, 0.0)
        for concept_a_raw, concept_b_raw, similarity in result.all():
            concept_a_id = self._coerce_uuid(concept_a_raw)
            concept_b_id = self._coerce_uuid(concept_b_raw)
            similarity_value = float(similarity)
            if concept_a_id in sigma_map and concept_b_id in context_ids:
                sigma_map[concept_a_id] = max(sigma_map[concept_a_id], similarity_value)
            if concept_b_id in sigma_map and concept_a_id in context_ids:
                sigma_map[concept_b_id] = max(sigma_map[concept_b_id], similarity_value)
        return sigma_map

    async def _due_concept_ids(self, *, user_id: UUID, course_id: UUID) -> set[UUID]:
        now = datetime.now(UTC)
        rows = await self._session.execute(
            select(CourseConcept.concept_id)
            .join(
                UserConceptState,
                and_(
                    UserConceptState.concept_id == CourseConcept.concept_id,
                    UserConceptState.user_id == user_id,
                ),
            )
            .where(
                and_(
                    CourseConcept.course_id == course_id,
                    UserConceptState.next_review_at.is_not(None),
                    UserConceptState.next_review_at <= now,
                )
            )
        )
        return set(rows.scalars().all())

    async def calculate_next_review(
        self,
        *,
        user_id: UUID,
        course_id: UUID,
        concept_id: UUID,
        rating: int,
        duration_ms: int | None = None,
    ) -> datetime:
        """Compute next review timestamp with sigma-based dampening (LECTOR §3.2)."""
        state = await self._session.scalar(
            select(UserConceptState).where(
                and_(
                    UserConceptState.user_id == user_id,
                    UserConceptState.concept_id == concept_id,
                )
            )
        )
        if state is None:
            state = UserConceptState(user_id=user_id, concept_id=concept_id)
            self._session.add(state)

        now = datetime.now(UTC)
        exposures = max(state.exposures, 0)
        base_minutes = float(self._settings.REVIEW_INTERVALS_BY_RATING.get(rating, 1440))
        multiplier = 1.0 + (exposures * self._settings.EXPOSURE_MULTIPLIER)
        if duration_ms is not None and duration_ms > 0:
            multiplier *= max(
                self._settings.DURATION_ADJUSTMENT_MIN,
                min(
                    self._settings.DURATION_ADJUSTMENT_MAX,
                    self._settings.DURATION_BASE_MS / max(duration_ms, 1000),
                ),
            )

        interval_minutes = base_minutes * multiplier

        recent_ids = await self._recent_concept_ids(user_id)
        due_ids = await self._due_concept_ids(user_id=user_id, course_id=course_id)
        context_ids = set(recent_ids) | due_ids
        context_ids.discard(concept_id)
        sigma = 0.0
        if context_ids:
            sigma = (await self._sigma_for_concepts({concept_id}, context_ids)).get(concept_id, 0.0)
        dampener = 1.0 / (1.0 + (self._confusion_lambda * sigma)) if sigma > 0 else 1.0
        interval_minutes = max(interval_minutes * dampener, 1.0)

        interval = timedelta(minutes=interval_minutes)
        next_review = now + interval
        state.next_review_at = next_review
        state.last_seen_at = now
        await self._session.flush()
        return next_review

    async def get_due_concepts(self, *, user_id: UUID, course_id: UUID) -> list[DueConceptEntry]:
        """Return concepts whose reviews are due."""
        now = datetime.now(UTC)
        rows = await self._session.execute(
            select(Concept, UserConceptState)
            .select_from(CourseConcept)
            .join(Concept, CourseConcept.concept_id == Concept.id)
            .join(
                UserConceptState,
                and_(
                    UserConceptState.concept_id == CourseConcept.concept_id,
                    UserConceptState.user_id == user_id,
                ),
            )
            .where(
                and_(
                    CourseConcept.course_id == course_id,
                    UserConceptState.next_review_at.is_not(None),
                    UserConceptState.next_review_at <= now,
                )
            )
        )

        due_entries: list[DueConceptEntry] = []
        for concept, state in rows.all():
            due_entries.append(
                DueConceptEntry(
                    concept=concept,
                    state=state,
                )
            )
        return due_entries

    async def update_learner_profile(
        self,
        *,
        user_id: UUID,
        concept_id: UUID,
        rating: int,
        duration_ms: int | None = None,
    ) -> dict[str, float]:
        """Apply exponential moving average updates to learner profile."""
        state = await self._session.scalar(
            select(UserConceptState).where(
                and_(
                    UserConceptState.user_id == user_id,
                    UserConceptState.concept_id == concept_id,
                )
            )
        )
        if state is None:
            state = UserConceptState(user_id=user_id, concept_id=concept_id)
            self._session.add(state)

        profile = dict(_DEFAULT_LEARNER_PROFILE)
        if state.learner_profile:
            profile.update(state.learner_profile)

        ema = LEARNER_PROFILE_EMA
        success = 1.0 if rating >= 3 else 0.0
        profile["success_rate"] = (1 - ema) * profile["success_rate"] + ema * success
        profile["retention_rate"] = (1 - ema) * profile["retention_rate"] + ema * (state.s_mastery)

        if duration_ms is not None and duration_ms > 0:
            speed = max(
                LEARNER_PROFILE_SPEED_MIN,
                min(
                    LEARNER_PROFILE_SPEED_MAX,
                    LEARNER_PROFILE_SPEED_BASE_MS / max(duration_ms, LEARNER_PROFILE_SPEED_FLOOR_MS),
                ),
            )
            profile["learning_speed"] = (1 - ema) * profile["learning_speed"] + ema * speed

        sensitivity_adjustment = (
            LEARNER_PROFILE_SENSITIVITY_DECAY if rating <= 2 else LEARNER_PROFILE_SENSITIVITY_BOOST
        )
        profile["semantic_sensitivity"] = max(
            LEARNER_PROFILE_SENSITIVITY_MIN,
            min(LEARNER_PROFILE_SENSITIVITY_MAX, profile["semantic_sensitivity"] * sensitivity_adjustment),
        )

        state.learner_profile = profile
        await self._session.flush()
        return profile
