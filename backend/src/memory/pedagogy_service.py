"""Read/merge logic for course-level teaching preferences.

Explicit learner-stated settings and inferred critique-derived conclusions are
stored in separate rows; merging happens at read time without losing
provenance. Explicit wins per field; avoid lists union.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.pedagogy_models import CourseTeachingProfile


TEACHING_PROFILE_FIELDS = (
    "pace_preference",
    "example_style",
    "quiz_density_preference",
    "visual_preference",
    "video_preference",
    "tone_preference",
)


@dataclass(frozen=True, slots=True)
class MergedTeachingValue:
    """One merged field value with the source it came from."""

    value: str
    source: str  # 'explicit' | 'inferred'


@dataclass(frozen=True, slots=True)
class MergedTeachingProfile:
    """Planner-facing merged view of a course's teaching preferences."""

    fields: dict[str, MergedTeachingValue] = field(default_factory=dict)
    avoid_list: list[str] = field(default_factory=list)

    def render_block(self) -> str:
        """Compact human-readable block ('' when empty)."""
        lines = [f"- {name} ({merged.source}): {merged.value}" for name, merged in sorted(self.fields.items())]
        if self.avoid_list:
            lines.append(f"- avoid: {', '.join(self.avoid_list)}")
        return "\n".join(lines)


async def upsert_course_teaching_profile(
    session: AsyncSession,
    *,
    course_id: uuid.UUID,
    source: str,
    avoid_list: list[str] | None = None,
    **fields_to_set: str | None,
) -> CourseTeachingProfile:
    """Create or update the course's profile row for one source.

    Only the passed fields change; pass an empty string to clear a field.
    """
    unknown = set(fields_to_set) - set(TEACHING_PROFILE_FIELDS)
    if unknown:
        msg = f"unknown teaching profile fields: {sorted(unknown)}"
        raise ValueError(msg)
    if source not in {"explicit", "inferred"}:
        msg = f"unknown teaching profile source: {source!r}"
        raise ValueError(msg)

    row = await session.scalar(
        select(CourseTeachingProfile)
        .where(CourseTeachingProfile.course_id == course_id, CourseTeachingProfile.source == source)
        .with_for_update()
    )
    if row is None:
        row = CourseTeachingProfile(course_id=course_id, source=source)
        session.add(row)

    for name, value in fields_to_set.items():
        if value is None:
            continue
        setattr(row, name, value.strip() or None)
    if avoid_list is not None:
        row.avoid_list = [item.strip() for item in avoid_list if item.strip()]

    await session.flush()
    return row


async def get_merged_teaching_profile(session: AsyncSession, course_id: uuid.UUID) -> MergedTeachingProfile:
    """Merge explicit and inferred rows; explicit wins per field, avoid lists union."""
    rows = list(
        await session.scalars(select(CourseTeachingProfile).where(CourseTeachingProfile.course_id == course_id))
    )
    by_source = {row.source: row for row in rows}

    merged_fields: dict[str, MergedTeachingValue] = {}
    for name in TEACHING_PROFILE_FIELDS:
        for source in ("explicit", "inferred"):
            row = by_source.get(source)
            value = getattr(row, name, None) if row is not None else None
            if value:
                merged_fields[name] = MergedTeachingValue(value=value, source=source)
                break

    avoid: list[str] = []
    for source in ("explicit", "inferred"):
        row = by_source.get(source)
        if row is not None:
            avoid.extend(item for item in row.avoid_list if item not in avoid)

    return MergedTeachingProfile(fields=merged_fields, avoid_list=avoid)


async def build_pedagogy_context(session: AsyncSession, *, user_id: uuid.UUID, course_id: uuid.UUID) -> str:
    """Planner-facing pedagogical context: teaching profile plus the StudentCard.

    The card is injected as-is (it already is the prompt block); the skeleton
    card with no claims is skipped. Mastery/review numbers stay in the adaptive
    signals and never appear here.
    """
    from src.memory.pedagogy_models import StudentCard
    from src.memory.student_card import DEFAULT_CARD_TEXT

    parts: list[str] = []

    profile_block = (await get_merged_teaching_profile(session, course_id)).render_block()
    if profile_block:
        parts.append(
            "Course teaching preferences (explicit = learner-stated, inferred = derived from critiques):\n"
            + profile_block
        )

    card = await session.scalar(
        select(StudentCard).where(StudentCard.user_id == user_id, StudentCard.course_id == course_id)
    )
    if card is not None and card.card_text.strip() != DEFAULT_CARD_TEXT:
        parts.append(
            "Student card (evidence-backed teaching memory for this learner; claims marked "
            "[hypothesis] or [tentative] are working theories to test, never hard facts; "
            "what the learner says they like and what measurably works are tracked separately):\n" + card.card_text
        )

    return "\n\n".join(parts)
