"""Re-derivation of StudentCard state from the revision log.

Revisions are append-only full-text snapshots written in the same transaction
as every card edit, so the latest snapshot IS the deterministic rebuild for a
given history — reconstruction is a single lookup, no LLM involved. Rebuilds
serve drift detection, repair, and sweeps; they never run on the request path.
Re-deriving claims from raw evidence is the updater's (LLM) job and only ever
runs forward over new evidence, never as a rebuild.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.pedagogy_models import StudentCard, StudentCardRevision
from src.memory.student_card import lock_card


@dataclass(frozen=True, slots=True)
class CardDrift:
    """One card whose live state disagrees with its latest revision snapshot."""

    card_id: uuid.UUID
    live_revision: int
    snapshot_revision: int | None
    live_text: str
    rebuilt_text: str | None


async def rebuild_card_text(session: AsyncSession, card_id: uuid.UUID) -> str | None:
    """Deterministic rebuild: the card text the revision log says is current.

    Older snapshots may be redacted in place (Phase 17); the rebuild only ever
    reads the latest snapshot, so redaction of history never changes it.
    """
    snapshot = await _latest_snapshot(session, card_id)
    return snapshot.card_text if snapshot is not None else None


async def diff_student_card(
    session: AsyncSession, *, user_id: uuid.UUID, course_id: uuid.UUID
) -> CardDrift | None:
    """Compare the live card against its latest snapshot; None when consistent."""
    card = await session.scalar(
        select(StudentCard).where(StudentCard.user_id == user_id, StudentCard.course_id == course_id)
    )
    if card is None:
        return None
    return _drift(card, await _latest_snapshot(session, card.id))


async def repair_student_card(
    session: AsyncSession, *, user_id: uuid.UUID, course_id: uuid.UUID
) -> CardDrift | None:
    """Restore live card_text/revision from the latest snapshot (one transaction).

    Runs under the same row lock the updater's edit session takes, so live
    writes cannot be lost: every edit snapshots first and swaps atomically, and
    an in-flight session holds the lock until its snapshot is committed.
    Returns the drift that was repaired, or None when already consistent.
    """
    card = await lock_card(session, user_id=user_id, course_id=course_id)
    drift = _drift(card, await _latest_snapshot(session, card.id))
    if drift is None or drift.rebuilt_text is None or drift.snapshot_revision is None:
        # No snapshot means nothing to restore from; surface the drift unrepaired.
        return drift

    card.card_text = drift.rebuilt_text
    card.revision = drift.snapshot_revision
    await session.flush()
    return drift


_DRIFTED_CARDS_SQL = text(
    """
    SELECT c.user_id, c.course_id
    FROM student_cards c
    LEFT JOIN LATERAL (
        SELECT r.revision, r.card_text
        FROM student_card_revisions r
        WHERE r.card_id = c.id
        ORDER BY r.revision DESC
        LIMIT 1
    ) latest ON TRUE
    WHERE c.revision IS DISTINCT FROM latest.revision
       OR c.card_text IS DISTINCT FROM latest.card_text
    """
)


async def find_drifted_cards(session: AsyncSession) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """All learner-course pairs whose live card disagrees with its latest snapshot."""
    result = await session.execute(_DRIFTED_CARDS_SQL)
    return [(row.user_id, row.course_id) for row in result]


async def _latest_snapshot(session: AsyncSession, card_id: uuid.UUID) -> StudentCardRevision | None:
    return await session.scalar(
        select(StudentCardRevision)
        .where(StudentCardRevision.card_id == card_id)
        .order_by(StudentCardRevision.revision.desc())
        .limit(1)
    )


def _drift(card: StudentCard, snapshot: StudentCardRevision | None) -> CardDrift | None:
    snapshot_revision = snapshot.revision if snapshot is not None else None
    rebuilt_text = snapshot.card_text if snapshot is not None else None
    if card.card_text == rebuilt_text and card.revision == snapshot_revision:
        return None
    return CardDrift(
        card_id=card.id,
        live_revision=card.revision,
        snapshot_revision=snapshot_revision,
        live_text=card.card_text,
        rebuilt_text=rebuilt_text,
    )
