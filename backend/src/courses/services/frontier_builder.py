"""Utilities for assembling the course concept frontier response."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.courses.models import Concept, Lesson, LessonVersion, UserConceptState
from src.courses.schemas import ConceptSummary, FrontierResponse

from .concept_graph_service import ConceptGraphService, FrontierEntry
from .concept_scheduler_service import DueConceptEntry, LectorSchedulerService


RecommendedLessonEntry = Literal["open_current", "start_next_pass"]


@dataclass(slots=True)
class _FrontierSnapshot:
    frontier: list[ConceptSummary]
    coming_soon: list[ConceptSummary]
    due_for_review: list[ConceptSummary]
    avg_mastery: float
    course_concepts: list[Concept]
    concept_by_id: dict[uuid.UUID, Concept]
    state_by_id: dict[uuid.UUID, UserConceptState]
    due_ids: set[uuid.UUID]


def _to_concept_summary(
    concept: Concept,
    state: UserConceptState | None,
    *,
    lesson_ids_by_concept: dict[uuid.UUID, uuid.UUID],
    recommended_lesson_entries: dict[uuid.UUID, RecommendedLessonEntry] | None = None,
    prerequisites: list[uuid.UUID] | None = None,
    order_hint: int | None = None,
) -> ConceptSummary:
    mastery = state.s_mastery if state is not None else None
    next_review = state.next_review_at if state is not None else None
    exposures = state.exposures if state is not None else 0
    lesson_id = lesson_ids_by_concept.get(concept.id)
    return ConceptSummary(
        id=concept.id,
        name=concept.name,
        description=concept.description,
        difficulty=concept.difficulty,
        mastery=mastery,
        next_review_at=next_review,
        exposures=exposures,
        lesson_id=lesson_id,
        recommended_lesson_entry=(recommended_lesson_entries or {}).get(concept.id),
        prerequisites=prerequisites or [],
        order=order_hint,
    )


def _prepare_frontier_snapshot(
    frontier_entries: Sequence[FrontierEntry],
    due_entries: Sequence[DueConceptEntry],
    *,
    lesson_ids_by_concept: dict[uuid.UUID, uuid.UUID],
    recommended_lesson_entries: dict[uuid.UUID, RecommendedLessonEntry],
) -> _FrontierSnapshot:
    entries = list(frontier_entries)
    due_list = list(due_entries)

    frontier: list[ConceptSummary] = []
    coming_soon: list[ConceptSummary] = []
    # Compute average mastery across ALL assigned concepts (treat missing state as 0.0)
    sum_mastery = 0.0

    course_concepts = [entry["concept"] for entry in entries]
    state_by_id = {
        entry["state"].concept_id: entry["state"]
        for entry in entries
        if entry["state"] is not None
    }
    concept_by_id = {concept.id: concept for concept in course_concepts}
    prereqs_by_id = {entry["concept"].id: entry["prerequisites"] for entry in entries}
    due_ids = {item["concept"].id for item in due_list}

    for entry in entries:
        concept: Concept = entry["concept"]
        state: UserConceptState | None = entry["state"]
        sum_mastery += float(state.s_mastery) if state is not None else 0.0
        summary = _to_concept_summary(
            concept,
            state,
            lesson_ids_by_concept=lesson_ids_by_concept,
            recommended_lesson_entries=recommended_lesson_entries,
            prerequisites=entry["prerequisites"],
            order_hint=entry["order_hint"],
        )
        # Due-for-review concepts belong in due_for_review, not frontier
        if concept.id in due_ids:
            continue
        if entry["unlocked"]:
            frontier.append(summary)
        else:
            coming_soon.append(summary)

    due_for_review = [
        _to_concept_summary(
            item["concept"],
            item["state"],
            lesson_ids_by_concept=lesson_ids_by_concept,
            recommended_lesson_entries=recommended_lesson_entries,
            prerequisites=prereqs_by_id.get(item["concept"].id, []),
            order_hint=item["order_hint"],
        )
        for item in due_list
    ]
    avg_mastery = (sum_mastery / len(course_concepts)) if course_concepts else 0.0

    return _FrontierSnapshot(
        frontier=frontier,
        coming_soon=coming_soon,
        due_for_review=due_for_review,
        avg_mastery=avg_mastery,
        course_concepts=course_concepts,
        concept_by_id=concept_by_id,
        state_by_id=state_by_id,
        due_ids=due_ids,
    )


async def _build_recommended_lesson_entries(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    scheduler_service: LectorSchedulerService,
    frontier_entries: Sequence[FrontierEntry],
    due_entries: Sequence[DueConceptEntry],
) -> dict[uuid.UUID, RecommendedLessonEntry]:
    candidate_concept_ids = {
        entry["concept"].id
        for entry in frontier_entries
        if entry["unlocked"]
    }
    candidate_concept_ids.update(item["concept"].id for item in due_entries)
    if not candidate_concept_ids:
        return {}

    lesson_rows = (
        await session.execute(
            select(
                Lesson.id,
                Lesson.concept_id,
                Lesson.content,
                Lesson.current_version_id,
                LessonVersion.major_version,
                LessonVersion.content,
            )
            .outerjoin(LessonVersion, LessonVersion.id == Lesson.current_version_id)
            .where(
                Lesson.course_id == course_id,
                Lesson.concept_id.in_(candidate_concept_ids),
            )
        )
    ).all()

    recommendations: dict[uuid.UUID, RecommendedLessonEntry] = {}
    for _, concept_id, lesson_content, _current_version_id, current_major_version, current_version_content in lesson_rows:
        if concept_id is None:
            continue

        current_pass_has_content = bool((current_version_content or lesson_content or "").strip())
        if not current_pass_has_content:
            recommendations[concept_id] = "open_current"
            continue

        recommendation = await scheduler_service.recommend_adaptive_pass(
            user_id=user_id,
            course_id=course_id,
            concept_id=concept_id,
            current_major_version=int(current_major_version or 1),
        )
        recommendations[concept_id] = (
            "start_next_pass"
            if recommendation.action == "deepen_with_next_major_pass"
            else "open_current"
        )

    return recommendations


async def build_course_frontier(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    graph_service: ConceptGraphService,
    scheduler_service: LectorSchedulerService,
) -> FrontierResponse:
    """Assemble the full frontier payload for a course."""
    lesson_rows = (
        await session.execute(
            select(Lesson.id, Lesson.concept_id).where(
                Lesson.course_id == course_id,
                Lesson.concept_id.is_not(None),
            )
        )
    ).all()
    lesson_ids_by_concept = {
        concept_id: lesson_id
        for lesson_id, concept_id in lesson_rows
        if concept_id is not None
    }
    frontier_entries = await graph_service.get_frontier(user_id=user_id, course_id=course_id)
    due_entries = await scheduler_service.get_due_concepts(user_id=user_id, course_id=course_id)
    ranked_due_entries = await scheduler_service.rank_due_entries(
        user_id=user_id,
        course_id=course_id,
        entries=due_entries,
    )
    ranked_frontier = await scheduler_service.rank_frontier_entries(
        user_id=user_id,
        entries=frontier_entries,
        due_entries=ranked_due_entries,
    )
    recommended_lesson_entries = await _build_recommended_lesson_entries(
        session=session,
        user_id=user_id,
        course_id=course_id,
        scheduler_service=scheduler_service,
        frontier_entries=ranked_frontier,
        due_entries=ranked_due_entries,
    )

    snapshot = _prepare_frontier_snapshot(
        ranked_frontier,
        ranked_due_entries,
        lesson_ids_by_concept=lesson_ids_by_concept,
        recommended_lesson_entries=recommended_lesson_entries,
    )

    return FrontierResponse(
        frontier=snapshot.frontier,
        due_for_review=snapshot.due_for_review,
        coming_soon=snapshot.coming_soon,
        due_count=len(snapshot.due_for_review),
        avg_mastery=snapshot.avg_mastery,
    )


__all__ = ["build_course_frontier"]
