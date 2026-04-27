
from collections.abc import Sequence
from dataclasses import dataclass
from operator import itemgetter

from sqlalchemy.ext.asyncio import AsyncSession

from .concept_graph_service import FrontierEntry


"""LECTOR scheduling service implementing semantic-aware spaced repetition.

Embedding-based confusors are computed and persisted at course creation (or
immediately after backfilling embeddings). The scheduler reads ConceptSimilarity
and does not compute on-the-fly fallback from embeddings.
"""


import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal, TypedDict

from sqlalchemy import and_, func, or_, select

from src.config.settings import get_settings
from src.courses.models import (
    _DEFAULT_LEARNER_PROFILE,
    Concept,
    ConceptPrerequisite,
    ConceptSimilarity,
    CourseConcept,
    ProbeEvent,
    UserConceptState,
)


logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


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
    order_hint: int | None


@dataclass(slots=True)
class AdaptivePassRecommendation:
    """High-level decision for how an adaptive lesson should behave on revisit."""

    action: Literal["review_now", "deepen_with_next_major_pass", "defer_for_now"]
    recommended_major_version: int
    reason: str


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
        user_id: uuid.UUID,
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
    def _coerce_uuid(value: object) -> uuid.UUID:
        """Normalize database-returned identifiers to uuid.UUID instances."""
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(str(value))
        except (TypeError, ValueError) as exc:
            message = f"Expected uuid.UUID-compatible value, got {value!r}"
            raise ValueError(message) from exc

    async def _recent_concept_ids(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        if self._risk_recent_k <= 0:
            return []
        rows = await self._session.execute(
            select(ProbeEvent.concept_id)
            .where(ProbeEvent.user_id == user_id)
            .order_by(ProbeEvent.ts.desc())
            .limit(self._risk_recent_k)
        )
        concepts = []
        seen: set[uuid.UUID] = set()
        for concept_id in rows.scalars():
            if concept_id not in seen:
                seen.add(concept_id)
                concepts.append(concept_id)
        return concepts

    async def _sigma_for_concepts(
        self,
        concept_ids: set[uuid.UUID],
        context_ids: set[uuid.UUID],
    ) -> dict[uuid.UUID, float]:
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

        sigma_map: dict[uuid.UUID, float] = dict.fromkeys(concept_ids, 0.0)
        for concept_a_raw, concept_b_raw, similarity in result.all():
            concept_a_id = self._coerce_uuid(concept_a_raw)
            concept_b_id = self._coerce_uuid(concept_b_raw)
            similarity_value = float(similarity)
            if concept_a_id in sigma_map and concept_b_id in context_ids:
                sigma_map[concept_a_id] = max(sigma_map[concept_a_id], similarity_value)
            if concept_b_id in sigma_map and concept_a_id in context_ids:
                sigma_map[concept_b_id] = max(sigma_map[concept_b_id], similarity_value)
        return sigma_map

    async def _due_concept_ids(self, *, user_id: uuid.UUID, course_id: uuid.UUID) -> set[uuid.UUID]:
        now = _utc_now()
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
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        concept_id: uuid.UUID,
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

        now = _utc_now()
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

    async def get_due_concepts(self, *, user_id: uuid.UUID, course_id: uuid.UUID) -> list[DueConceptEntry]:
        """Return concepts whose reviews are due."""
        now = _utc_now()
        rows = await self._session.execute(
            select(Concept, UserConceptState, CourseConcept.order_hint)
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
        for concept, state, order_hint in rows.all():
            due_entries.append(
                DueConceptEntry(
                    concept=concept,
                    state=state,
                    order_hint=order_hint,
                )
            )
        return due_entries

    async def rank_due_entries(
        self,
        *,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        entries: Sequence[DueConceptEntry],
    ) -> list[DueConceptEntry]:
        """Return due concepts in a stable learner-priority order."""
        entry_list = list(entries)
        if len(entry_list) <= 1:
            return entry_list

        now = _utc_now()
        recent_ids = await self._recent_concept_ids(user_id)
        due_ids = {item["concept"].id for item in entry_list}
        sigma_map = await self._sigma_for_concepts(due_ids, set(recent_ids) | due_ids)

        ranked_entries: list[tuple[tuple[float, float, str], DueConceptEntry]] = []
        for entry in entry_list:
            state = entry["state"]
            next_review_at = state.next_review_at or now
            if next_review_at.tzinfo is None:
                next_review_at = next_review_at.replace(tzinfo=UTC)

            hours_overdue = max(0.0, (now - next_review_at).total_seconds() / 3600)
            mastery = self._mastery_value(state)
            sigma_value = sigma_map.get(entry["concept"].id, 0.0)
            downstream_pressure = await self._downstream_pressure(
                user_id=user_id,
                course_id=course_id,
                concept_id=entry["concept"].id,
            )
            identifier = (entry["concept"].name or "").strip().lower() or (entry["concept"].slug or "").strip().lower()
            key = (
                -(hours_overdue + downstream_pressure + ((1.0 - mastery) * 2.0) - (sigma_value * 0.2)),
                next_review_at.timestamp(),
                identifier,
            )
            ranked_entries.append((key, entry))

        ranked_entries.sort(key=itemgetter(0))
        return [entry for _, entry in ranked_entries]

    async def recommend_adaptive_pass(
        self,
        *,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        concept_id: uuid.UUID,
        current_major_version: int,
    ) -> AdaptivePassRecommendation:
        """Decide whether a revisit should stay review-only or deepen into a new pass."""
        state = await self._session.scalar(
            select(UserConceptState).where(
                and_(
                    UserConceptState.user_id == user_id,
                    UserConceptState.concept_id == concept_id,
                )
            )
        )
        if state is None:
            return AdaptivePassRecommendation(
                action="review_now",
                recommended_major_version=max(current_major_version, 1),
                reason="No learner history exists for this concept yet.",
            )

        mastery = self._mastery_value(state)
        exposures = max(state.exposures, 0)
        recent_accuracy = await self._recent_accuracy(user_id=user_id, concept_id=concept_id)
        downstream_pressure = await self._downstream_pressure(
            user_id=user_id,
            course_id=course_id,
            concept_id=concept_id,
        )
        downstream_miss_count = await self._downstream_recent_miss_count(user_id=user_id, course_id=course_id, concept_id=concept_id)
        competing_due_count = len((await self._due_concept_ids(user_id=user_id, course_id=course_id)) - {concept_id})
        semantic_confusion = await self._current_confusion_pressure(user_id=user_id, course_id=course_id, concept_id=concept_id)

        now = _utc_now()
        review_is_due = False
        if state.next_review_at is not None:
            next_review_at = state.next_review_at
            if next_review_at.tzinfo is None:
                next_review_at = next_review_at.replace(tzinfo=UTC)
            review_is_due = next_review_at <= now

        should_deepen = (
            review_is_due
            and exposures >= max(current_major_version, 1)
            and mastery >= 0.76
            and (recent_accuracy is None or recent_accuracy >= 0.6)
            and (downstream_pressure > 0.0 or downstream_miss_count > 0 or semantic_confusion >= 0.45 or mastery >= 0.9)
            and competing_due_count <= 1
        )
        if should_deepen:
            return AdaptivePassRecommendation(
                action="deepen_with_next_major_pass",
                recommended_major_version=current_major_version + 1,
                reason="The learner is retaining this concept well enough for a broader revisit that still reviews the core idea.",
            )

        if not review_is_due and mastery >= 0.9 and competing_due_count > 0 and downstream_pressure <= 0.01:
            return AdaptivePassRecommendation(
                action="defer_for_now",
                recommended_major_version=current_major_version,
                reason="Other concepts need attention sooner than this already-strong concept.",
            )

        return AdaptivePassRecommendation(
            action="review_now",
            recommended_major_version=current_major_version,
            reason="The learner still benefits more from review than from a new major pass right now.",
        )

    async def _recent_accuracy(self, *, user_id: uuid.UUID, concept_id: uuid.UUID) -> float | None:
        outcomes = (
            (
                await self._session.execute(
                    select(ProbeEvent.correct)
                    .where(
                        ProbeEvent.user_id == user_id,
                        ProbeEvent.concept_id == concept_id,
                    )
                    .order_by(ProbeEvent.ts.desc())
                    .limit(5)
                )
            )
            .scalars()
            .all()
        )
        if not outcomes:
            return None
        return sum(1 for outcome in outcomes if outcome) / len(outcomes)

    async def _downstream_pressure(self, *, user_id: uuid.UUID, course_id: uuid.UUID, concept_id: uuid.UUID) -> float:
        rows = (
            await self._session.execute(
                select(UserConceptState.s_mastery)
                .select_from(ConceptPrerequisite)
                .join(
                    CourseConcept,
                    and_(
                        CourseConcept.concept_id == ConceptPrerequisite.concept_id,
                        CourseConcept.course_id == course_id,
                    ),
                )
                .outerjoin(
                    UserConceptState,
                    and_(
                        UserConceptState.concept_id == ConceptPrerequisite.concept_id,
                        UserConceptState.user_id == user_id,
                    ),
                )
                .where(ConceptPrerequisite.prereq_id == concept_id)
            )
        ).scalars().all()
        if not rows:
            return 0.0

        pressure = 0.0
        for mastery in rows:
            mastery_value = float(mastery) if mastery is not None else 0.0
            if mastery_value < self._unlock_threshold:
                pressure += 1.0 - mastery_value
        return round(pressure, 3)

    async def _downstream_recent_miss_count(
        self,
        *,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        concept_id: uuid.UUID,
    ) -> int:
        downstream_ids = (
            (
                await self._session.execute(
                    select(ConceptPrerequisite.concept_id)
                    .join(
                        CourseConcept,
                        and_(
                            CourseConcept.concept_id == ConceptPrerequisite.concept_id,
                            CourseConcept.course_id == course_id,
                        ),
                    )
                    .where(ConceptPrerequisite.prereq_id == concept_id)
                )
            )
            .scalars()
            .all()
        )
        if not downstream_ids:
            return 0

        recent_misses = await self._session.scalar(
            select(func.count())
            .select_from(ProbeEvent)
            .where(
                ProbeEvent.user_id == user_id,
                ProbeEvent.concept_id.in_(downstream_ids),
                ProbeEvent.correct.is_(False),
            )
        )
        return int(recent_misses or 0)

    async def _current_confusion_pressure(
        self,
        *,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        concept_id: uuid.UUID,
    ) -> float:
        context_ids = (await self._due_concept_ids(user_id=user_id, course_id=course_id)) - {concept_id}
        if not context_ids:
            recent_ids = await self._recent_concept_ids(user_id)
            context_ids = set(recent_ids) - {concept_id}
        if not context_ids:
            return 0.0
        sigma_map = await self._sigma_for_concepts({concept_id}, context_ids)
        return float(sigma_map.get(concept_id, 0.0))

    async def update_learner_profile(
        self,
        *,
        user_id: uuid.UUID,
        concept_id: uuid.UUID,
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
