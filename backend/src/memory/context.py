"""One composer for all injected memory text.

A call's memory scope is exactly ``(user_id, course_id)``: the profile lane
(custom instructions + slots) always applies; the pedagogy lane (teaching
profile + StudentCard) joins when the call is course-scoped. This module owns
all framing; the LLM client injects the composed block verbatim under the
single applicability wrapper. It lives at the package top level because it
spans both lanes — putting it inside either would make the lanes import each
other.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.models import StudentCard
from src.memory.services import pedagogy_service, profile_service
from src.memory.services.student_card import DEFAULT_CARD_TEXT


async def compose_memory_context(
    session: AsyncSession, user_id: uuid.UUID, course_id: uuid.UUID | None = None
) -> str:
    """All durable memory one call may see, framed and merged ('' when empty).

    Custom instructions and profile slots are never injected as parallel
    sources; mastery/review numbers stay in the adaptive signals and never
    appear here.
    """
    parts: list[str] = []

    instructions = await profile_service.get_custom_instructions(session, user_id)
    if instructions:
        parts.append(f"User custom instructions:\n{instructions}")

    profile_block = profile_service.build_profile_block(await profile_service.get_active_slots(session, user_id))
    if profile_block:
        parts.append(f"User profile (durable preferences):\n{profile_block}")

    if course_id is not None:
        parts.extend(await _pedagogy_parts(session, user_id=user_id, course_id=course_id))

    return "\n\n".join(parts)


async def _pedagogy_parts(session: AsyncSession, *, user_id: uuid.UUID, course_id: uuid.UUID) -> list[str]:
    """Course-scoped teaching memory: merged teaching profile plus the StudentCard.

    The card is injected as-is (it already is the prompt block); the skeleton
    card with no claims is skipped.
    """
    parts: list[str] = []

    profile_block = (await pedagogy_service.get_merged_teaching_profile(session, course_id)).render_block()
    if profile_block:
        parts.append(
            "Course teaching preferences (explicit = learner-stated, inferred = derived from critiques):\n"
            + profile_block
        )

    card = await session.scalar(
        select(StudentCard).where(StudentCard.user_id == user_id, StudentCard.course_id == course_id)
    )
    if card is not None and card.deleted_at is None and card.card_text.strip() != DEFAULT_CARD_TEXT:
        parts.append(
            "Student card (evidence-backed teaching memory for this learner; claims marked "
            "[hypothesis] or [tentative] are working theories to test, never hard facts; "
            "what the learner says they like and what measurably works are tracked separately):\n" + card.card_text
        )

    return parts
