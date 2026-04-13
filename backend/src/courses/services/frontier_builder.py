"""Utilities for assembling the course concept frontier response."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.courses.models import Concept, Lesson, UserConceptState
from src.courses.schemas import ConceptSummary, FrontierResponse

from .concept_graph_service import ConceptGraphService, FrontierEntry
from .concept_scheduler_service import DueConceptEntry, LectorSchedulerService


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
    prerequisites: list[uuid.UUID] | None = None,
) -> ConceptSummary:
    mastery = state.s_mastery if state is not None else None
    next_review = state.next_review_at if state is not None else None
    exposures = state.exposures if state is not None else 0
    lesson_id = lesson_ids_by_concept.get(concept.id)
    return ConceptSummary(
        id=concept.id,
        name=concept.name,
        description=concept.description,
        difficulty=None,  # Not available in Concept model
        mastery=mastery,
        next_review_at=next_review,
        exposures=exposures,
        lesson_id=lesson_id,
        prerequisites=prerequisites or [],
        order=None,  # Not available in this context
    )


def _prepare_frontier_snapshot(
    frontier_entries: Sequence[FrontierEntry],
    due_entries: Sequence[DueConceptEntry],
    *,
    lesson_ids_by_concept: dict[uuid.UUID, uuid.UUID],
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

    for entry in entries:
        concept: Concept = entry["concept"]
        state: UserConceptState | None = entry["state"]
        sum_mastery += float(state.s_mastery) if state is not None else 0.0
        summary = _to_concept_summary(
            concept,
            state,
            lesson_ids_by_concept=lesson_ids_by_concept,
            prerequisites=entry["prerequisites"],
        )
        if entry["unlocked"]:
            frontier.append(summary)
        else:
            coming_soon.append(summary)

    due_for_review = [
        _to_concept_summary(
            item["concept"],
            item["state"],
            lesson_ids_by_concept=lesson_ids_by_concept,
            prerequisites=prereqs_by_id.get(item["concept"].id, []),
        )
        for item in due_list
    ]
    avg_mastery = (sum_mastery / len(course_concepts)) if course_concepts else 0.0
    due_ids = {item["concept"].id for item in due_list}

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

    snapshot = _prepare_frontier_snapshot(
        ranked_frontier,
        ranked_due_entries,
        lesson_ids_by_concept=lesson_ids_by_concept,
    )

    return FrontierResponse(
        frontier=snapshot.frontier,
        due_for_review=snapshot.due_for_review,
        coming_soon=snapshot.coming_soon,
        due_count=len(snapshot.due_for_review),
        avg_mastery=snapshot.avg_mastery,
    )


__all__ = ["build_course_frontier"]
