"""Thin writer for the append-only teaching event log.

Records what was shown to the learner and how they responded, in the same
session/transaction as the flow that produced the evidence. No LLM; the only
logic is a cheap threshold check that nudges the sleep-time updater.
"""

from __future__ import annotations

import uuid

from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.pedagogy_models import TeachingEvent


TEACHING_EVENT_TYPES = frozenset(
    {
        "lesson_version_shown",
        "check_answered",
        "lesson_regenerated",
        "lesson_completed",
        "delayed_outcome",
        "preference_stated",
    }
)


async def record_teaching_event(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    event_type: str,
    lesson_id: uuid.UUID | None = None,
    lesson_version_id: uuid.UUID | None = None,
    concept_id: uuid.UUID | None = None,
    strategy_label: str | None = None,
    window_count: int | None = None,
    duration_ms: int | None = None,
    hints_used: int | None = None,
    outcome: str | None = None,
    details: dict[str, JsonValue] | None = None,
) -> TeachingEvent:
    """Append one teaching event row in the caller's transaction and return it."""
    if event_type not in TEACHING_EVENT_TYPES:
        msg = f"unknown teaching event type: {event_type}"
        raise ValueError(msg)

    event = TeachingEvent(
        user_id=user_id,
        course_id=course_id,
        event_type=event_type,
        lesson_id=lesson_id,
        lesson_version_id=lesson_version_id,
        concept_id=concept_id,
        strategy_label=strategy_label,
        window_count=window_count,
        duration_ms=duration_ms,
        hints_used=hints_used,
        outcome=outcome,
        details=details if details is not None else {},
    )
    session.add(event)
    await session.flush()

    # Local import: the updater module pulls in jobs and course models.
    from src.memory.pedagogy_updater import maybe_trigger_update

    # The learner speaking in their own words is high-signal: consolidate now.
    high_signal = event_type in {"lesson_regenerated", "preference_stated"}
    await maybe_trigger_update(session, user_id=user_id, course_id=course_id, high_signal=high_signal)
    return event
