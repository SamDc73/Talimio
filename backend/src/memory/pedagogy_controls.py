"""Learner-facing pedagogical memory controls: inspect, suppress, forget.

Inspect surfaces the merged teaching profile (with per-field source) and the
StudentCard claims exactly as stored — each claim line already carries its
lifecycle, confidence, and evidence refs as plain text, which IS the
provenance display. Suppress removes one claim line through the same
text-editor edit path the updater uses. Forget soft-deletes the card and the
inferred profile immediately in the caller's transaction, then defers an
async cascade that redacts learner-authored evidence (critiques and card
revision snapshots); system-measured teaching events survive as minimal
structural records.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import BadRequestError
from src.jobs import QUEUE_MAINTENANCE, defer_job
from src.memory.pedagogy_models import CourseTeachingProfile, StudentCard, StudentCardRevision
from src.memory.pedagogy_service import get_merged_teaching_profile
from src.memory.student_card import SECTION_HEADERS, CardEditError, card_replace, lock_card


PEDAGOGY_FORGET_TASK_NAME = "pedagogy.forget_cleanup"

_REDACTED = "[redacted]"


def forget_queueing_lock(user_id: uuid.UUID | str, course_id: uuid.UUID | str) -> str:
    """Queueing lock that collapses duplicate forget cascades per learner-course pair."""
    return f"pedagogy:forget:{user_id}:{course_id}"


@dataclass(frozen=True, slots=True)
class TeachingProfileField:
    """One merged teaching-profile field with its provenance source."""

    name: str
    value: str
    source: str  # 'explicit' | 'inferred'


@dataclass(frozen=True, slots=True)
class PedagogicalMemoryView:
    """Everything pedagogical memory knows about one learner-course pair."""

    teaching_profile: list[TeachingProfileField] = field(default_factory=list)
    avoid_list: list[str] = field(default_factory=list)
    card_text: str | None = None
    card_revision: int | None = None
    card_updated_at: datetime | None = None
    claims: dict[str, list[str]] = field(default_factory=dict)


async def get_pedagogical_memory(
    session: AsyncSession, *, user_id: uuid.UUID, course_id: uuid.UUID
) -> PedagogicalMemoryView:
    """Assemble the learner-facing view: profile with sources plus parsed card claims."""
    merged = await get_merged_teaching_profile(session, course_id)
    teaching_profile = [
        TeachingProfileField(name=name, value=value.value, source=value.source)
        for name, value in sorted(merged.fields.items())
    ]

    card = await session.scalar(
        select(StudentCard).where(StudentCard.user_id == user_id, StudentCard.course_id == course_id)
    )
    if card is None or card.deleted_at is not None:
        return PedagogicalMemoryView(teaching_profile=teaching_profile, avoid_list=list(merged.avoid_list))

    return PedagogicalMemoryView(
        teaching_profile=teaching_profile,
        avoid_list=list(merged.avoid_list),
        card_text=card.card_text,
        card_revision=card.revision,
        card_updated_at=card.updated_at,
        claims=parse_card_claims(card.card_text),
    )


def parse_card_claims(card_text: str) -> dict[str, list[str]]:
    """Claim lines per section, verbatim; each line is its own provenance display.

    Only bullet lines count as claims, so the "(none yet)" placeholder is skipped.
    """
    claims: dict[str, list[str]] = {header: [] for header in SECTION_HEADERS}
    current: list[str] | None = None
    for raw_line in card_text.splitlines():
        line = raw_line.strip()
        if line in claims:
            current = claims[line]
        elif current is not None and line.startswith("- "):
            current.append(line)
    return claims


async def suppress_claim(session: AsyncSession, *, user_id: uuid.UUID, course_id: uuid.UUID, claim_text: str) -> int:
    """Remove exactly one claim line from the live card; returns the new revision.

    Raw measured outcomes (teaching_events) are untouched by suppression.
    """
    card = await lock_card(session, user_id=user_id, course_id=course_id)
    try:
        try:
            # Take the trailing newline with the claim so no blank line is left behind.
            await card_replace(session, card, old_str=f"{claim_text}\n", new_str="")
        except CardEditError:
            await card_replace(session, card, old_str=claim_text, new_str="")
    except CardEditError as error:
        raise BadRequestError(str(error)) from error
    return card.revision


async def forget_pedagogical_memory(session: AsyncSession, *, user_id: uuid.UUID, course_id: uuid.UUID) -> None:
    """Forget pedagogical memory now; the deferred cascade redacts evidence after commit.

    Immediate, in the caller's transaction: soft-delete the card and drop the
    inferred teaching-profile row (explicit learner-stated settings stay).
    """
    # Barrier first: blocks on the watermark row until any in-flight updater
    # commits, and stops pending jobs from rebuilding the card from
    # pre-forget evidence. Monotonic via GREATEST.
    forget_cutoff = (
        await session.execute(
            text(
                """
                INSERT INTO pedagogy_watermarks (user_id, course_id, last_processed_at)
                VALUES (
                    :user_id,
                    :course_id,
                    GREATEST(
                        clock_timestamp(),
                        COALESCE((SELECT MAX(created_at) FROM teaching_events
                                  WHERE user_id = :user_id AND course_id = :course_id), 'epoch'),
                        COALESCE((SELECT MAX(created_at) FROM lesson_feedback_events
                                  WHERE course_id = :course_id), 'epoch')
                    )
                )
                ON CONFLICT (user_id, course_id) DO UPDATE
                SET last_processed_at = GREATEST(pedagogy_watermarks.last_processed_at, EXCLUDED.last_processed_at),
                    updated_at = NOW()
                RETURNING last_processed_at
                """
            ),
            {"user_id": user_id, "course_id": course_id},
        )
    ).scalar_one()

    card = await session.scalar(
        select(StudentCard).where(StudentCard.user_id == user_id, StudentCard.course_id == course_id).with_for_update()
    )
    if card is not None:
        card.deleted_at = datetime.now(UTC)

    await session.execute(
        delete(CourseTeachingProfile).where(
            CourseTeachingProfile.course_id == course_id,
            CourseTeachingProfile.source == "inferred",
        )
    )

    await defer_job(
        session,
        task_name=PEDAGOGY_FORGET_TASK_NAME,
        queue=QUEUE_MAINTENANCE,
        args={"user_id": str(user_id), "course_id": str(course_id), "cutoff": forget_cutoff.isoformat()},
        queueing_lock=forget_queueing_lock(user_id, course_id),
    )
    await session.flush()


async def run_forget_cleanup(user_id: uuid.UUID, course_id: uuid.UUID, cutoff: datetime) -> None:
    """Async forget cascade (worker entry): redact learner-authored evidence.

    Every redaction is bounded by ``cutoff`` (the watermark value the forget
    barrier committed), so evidence the learner creates after forgetting is
    never swept up by a late-running cascade. Critique text and extracted
    facets are redacted in place; ``facets_extracted_at`` stays so the updater
    never re-extracts. Card revision snapshots are blanked but keep their
    structural rows, and retrieval notes are redacted and tombstoned so search
    never returns them. Teaching events are system-measured outcomes and
    survive untouched.
    """
    from src.courses.models import LessonFeedbackEvent
    from src.database.session import async_session_maker

    async with async_session_maker() as session:
        await session.execute(
            update(LessonFeedbackEvent)
            .where(LessonFeedbackEvent.course_id == course_id, LessonFeedbackEvent.created_at <= cutoff)
            .values(
                critique_text=_REDACTED,
                pace_signal=None,
                modality_signal=None,
                example_style_signal=None,
                quiz_density_signal=None,
                tone_signal=None,
                strategy_request_signal=None,
            )
        )

        from src.memory.pedagogy_models import PedagogicalNote

        await session.execute(
            update(PedagogicalNote)
            .where(
                PedagogicalNote.user_id == user_id,
                PedagogicalNote.course_id == course_id,
                PedagogicalNote.deleted_at.is_(None),
                PedagogicalNote.created_at <= cutoff,
            )
            .values(note=_REDACTED, scene_trace=_REDACTED, verbatim_quote="", deleted_at=datetime.now(UTC))
        )

        card_id = await session.scalar(
            select(StudentCard.id).where(StudentCard.user_id == user_id, StudentCard.course_id == course_id)
        )
        if card_id is not None:
            await session.execute(
                update(StudentCardRevision)
                .where(StudentCardRevision.card_id == card_id, StudentCardRevision.created_at <= cutoff)
                .values(card_text=_REDACTED, tool_call={})
            )

        await session.commit()
