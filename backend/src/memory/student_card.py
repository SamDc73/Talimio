"""StudentCard storage and text-editor edit semantics.

The card is one labeled plain-text block (markdown sections) per user+course —
already the prompt block, human-readable and diffable. Edits use the
text-editor operations: ``replace`` (exact match + uniqueness)
and ``rethink`` (whole-block consolidation). App code validates every edit
(match found, unique, char limits, section labels intact) and commits; a
failed edit raises :class:`CardEditError` whose message goes back to the model
on the next tool turn. Untouched text survives by construction.

Claim lines inside sections carry lifecycle and provenance as plain text, e.g.
``- prefers worked examples before theory (supported 4x, last 2026-06-08; ev:1234) [supported]``.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.pedagogy_models import StudentCard, StudentCardRevision


SECTION_HEADERS = (
    "## Stated preferences",
    "## Observed effective patterns",
    "## Current working strategies",
    "## Known friction",
    "## Helpful / harmful media contexts",
    "## Open hypotheses to test",
    "## Strategy switch triggers",
)

SECTION_CHAR_LIMIT = 1500
CARD_CHAR_LIMIT = 8000

DEFAULT_CARD_TEXT = "\n\n".join(f"{header}\n(none yet)" for header in SECTION_HEADERS)


class CardEditError(ValueError):
    """A rejected card edit; the message is the feedback for the model."""


async def get_or_create_card(session: AsyncSession, *, user_id: uuid.UUID, course_id: uuid.UUID) -> StudentCard:
    """Load the learner-course card, creating the empty skeleton on first use."""
    card = await session.scalar(
        select(StudentCard).where(StudentCard.user_id == user_id, StudentCard.course_id == course_id)
    )
    if card is None:
        card = StudentCard(user_id=user_id, course_id=course_id, card_text=DEFAULT_CARD_TEXT, revision=1)
        session.add(card)
        await session.flush()
        session.add(_revision_row(card, tool="student_card_create", payload={}))
        await session.flush()
    return card


async def lock_card(session: AsyncSession, *, user_id: uuid.UUID, course_id: uuid.UUID) -> StudentCard:
    """Load the card under row-level lock for an edit session."""
    card = await session.scalar(
        select(StudentCard).where(StudentCard.user_id == user_id, StudentCard.course_id == course_id).with_for_update()
    )
    if card is None:
        return await get_or_create_card(session, user_id=user_id, course_id=course_id)
    return card


async def card_replace(
    session: AsyncSession,
    card: StudentCard,
    *,
    old_str: str,
    new_str: str,
    evidence_refs: list[JsonValue] | None = None,
) -> StudentCard:
    """Exact-match replace with uniqueness check."""
    if not old_str:
        msg = "old_str must be non-empty"
        raise CardEditError(msg)

    occurrences = card.card_text.count(old_str)
    if occurrences == 0:
        msg = f"old_str not found in card: {old_str[:120]!r}"
        raise CardEditError(msg)
    if occurrences > 1:
        msg = f"old_str occurs {occurrences} times; provide a longer, unique snippet"
        raise CardEditError(msg)

    new_text = card.card_text.replace(old_str, new_str, 1)
    _validate_card_text(new_text)
    return await _commit_edit(
        session,
        card,
        new_text=new_text,
        tool="student_card_replace",
        payload={"old_str": old_str, "new_str": new_str},
        evidence_refs=evidence_refs,
    )


async def card_rethink(
    session: AsyncSession,
    card: StudentCard,
    *,
    new_text: str,
    evidence_refs: list[JsonValue] | None = None,
) -> StudentCard:
    """Whole-block consolidation rewrite; all section labels must survive."""
    _validate_card_text(new_text)
    return await _commit_edit(
        session,
        card,
        new_text=new_text,
        tool="student_card_rethink",
        payload={"new_text": new_text},
        evidence_refs=evidence_refs,
    )


async def get_card_revisions(session: AsyncSession, card_id: uuid.UUID) -> list[StudentCardRevision]:
    """Revision history, oldest first."""
    stmt = (
        select(StudentCardRevision).where(StudentCardRevision.card_id == card_id).order_by(StudentCardRevision.revision)
    )
    return list(await session.scalars(stmt))


def _validate_card_text(text: str) -> None:
    stripped = text.strip()
    if not stripped:
        msg = "card text must not be empty"
        raise CardEditError(msg)
    if len(stripped) > CARD_CHAR_LIMIT:
        msg = f"card exceeds {CARD_CHAR_LIMIT} chars ({len(stripped)}); consolidate with student_card_rethink"
        raise CardEditError(msg)

    positions: list[int] = []
    for header in SECTION_HEADERS:
        position = stripped.find(header)
        if position < 0:
            msg = f"required section label missing: {header!r}"
            raise CardEditError(msg)
        positions.append(position)
    if positions != sorted(positions):
        msg = "section labels must stay in their canonical order"
        raise CardEditError(msg)

    for header, body in _sections(stripped).items():
        if len(body) > SECTION_CHAR_LIMIT:
            msg = f"section {header!r} exceeds {SECTION_CHAR_LIMIT} chars ({len(body)}); prune or consolidate"
            raise CardEditError(msg)


def _sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    for index, header in enumerate(SECTION_HEADERS):
        start = text.find(header) + len(header)
        end = text.find(SECTION_HEADERS[index + 1]) if index + 1 < len(SECTION_HEADERS) else len(text)
        sections[header] = text[start:end].strip()
    return sections


def _revision_row(
    card: StudentCard,
    *,
    tool: Literal["student_card_create", "student_card_replace", "student_card_rethink"],
    payload: dict[str, JsonValue],
    evidence_refs: list[JsonValue] | None = None,
) -> StudentCardRevision:
    return StudentCardRevision(
        card_id=card.id,
        revision=card.revision,
        card_text=card.card_text,
        tool_call={"tool": tool, **payload},
        evidence_refs=evidence_refs or [],
    )


async def _commit_edit(
    session: AsyncSession,
    card: StudentCard,
    *,
    new_text: str,
    tool: Literal["student_card_replace", "student_card_rethink"],
    payload: dict[str, JsonValue],
    evidence_refs: list[JsonValue] | None,
) -> StudentCard:
    card.card_text = new_text.strip()
    card.revision += 1
    await session.flush()
    session.add(_revision_row(card, tool=tool, payload=payload, evidence_refs=evidence_refs))
    await session.flush()
    return card
