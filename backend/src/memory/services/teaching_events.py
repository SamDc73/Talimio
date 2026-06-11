"""Writers for the two pedagogical evidence streams.

Evidence splits by nature, not by entry point. Learner-authored evidence
(regenerate critiques, chat-stated course preferences) lands in
``lesson_feedback_events`` and consolidates immediately — the learner speaking
in their own words is always high-signal. System-measured evidence (checks,
completions, outcomes) lands in ``teaching_events`` and consolidates on a
threshold or nightly. Both writers run in the caller's transaction; no LLM.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.models import TeachingEvent


if TYPE_CHECKING:
    from src.courses.models import LessonFeedbackEvent


TEACHING_EVENT_TYPES = frozenset(
    {
        "lesson_version_shown",
        "check_answered",
        "lesson_regenerated",
        "lesson_completed",
        "delayed_outcome",
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
    """Append one system-measured event row in the caller's transaction and return it."""
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
    from src.memory.services.pedagogy_updater import maybe_trigger_update

    await maybe_trigger_update(session, user_id=user_id, course_id=course_id)
    return event


async def record_course_feedback(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    critique_text: str,
    lesson_id: uuid.UUID | None = None,
    lesson_version_id: uuid.UUID | None = None,
) -> LessonFeedbackEvent:
    """Append one learner-authored feedback row and defer consolidation immediately.

    ``user_id`` only addresses the consolidation job (the row itself carries no
    user_id; the course implies its owner).
    """
    from src.courses.models import LessonFeedbackEvent
    from src.memory.services.pedagogy_updater import defer_pedagogy_update

    event = LessonFeedbackEvent(
        course_id=course_id,
        lesson_id=lesson_id,
        lesson_version_id=lesson_version_id,
        critique_text=critique_text,
    )
    session.add(event)
    await session.flush()

    await defer_pedagogy_update(session, user_id=user_id, course_id=course_id)
    return event
