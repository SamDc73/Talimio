"""Re-derivation of canonical profile state from the evidence log.

The evidence log records every committed inferred decision, so replaying
`applied` events in commit order deterministically reconstructs what the
inferred canonical state should be — no LLM involved. Rebuilds serve drift
detection, repair, and offline evaluation; they never run on the request path.

Manual slots have no evidence events (the user's edit is its own provenance),
so rebuilds only ever compare and repair inferred-source state.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.models import UserProfileSlot, UserProfileSlotEvent


@dataclass(frozen=True, slots=True)
class SlotDrift:
    """One slot where live inferred state disagrees with the evidence replay."""

    slot: str
    live_value: str | None
    rebuilt_value: str | None


async def rebuild_inferred_profile(session: AsyncSession, user_id: uuid.UUID) -> dict[str, str]:
    """Fold committed evidence events into the inferred profile they imply.

    Replays only `applied` events, in commit order (commit order is monotonic
    with source-evidence ordering by construction). A redacted set event whose
    proposed value was tombstoned replays as a clear: state that can no longer
    be re-derived from evidence must not survive a rebuild.
    """
    stmt = (
        select(UserProfileSlotEvent)
        .where(UserProfileSlotEvent.user_id == user_id, UserProfileSlotEvent.status == "applied")
        .order_by(UserProfileSlotEvent.created_at, UserProfileSlotEvent.id)
    )
    state: dict[str, str] = {}
    for event in await session.scalars(stmt):
        if event.op == "set" and event.proposed_value:
            state[event.slot] = event.proposed_value
        else:
            state.pop(event.slot, None)
    return state


async def diff_inferred_profile(session: AsyncSession, user_id: uuid.UUID) -> list[SlotDrift]:
    """Compare live inferred slots against the evidence replay.

    Slots currently pinned by an active manual value are excluded: manual wins
    until the user changes it, so inferred history is not drift there.
    """
    rebuilt = await rebuild_inferred_profile(session, user_id)
    live_rows = list(
        await session.scalars(
            select(UserProfileSlot).where(UserProfileSlot.user_id == user_id, UserProfileSlot.is_active)
        )
    )
    manual_slots = {row.slot for row in live_rows if row.source != "inferred"}
    live = {row.slot: row.value for row in live_rows if row.source == "inferred"}

    return [
        SlotDrift(slot=slot, live_value=live.get(slot), rebuilt_value=rebuilt.get(slot))
        for slot in sorted((set(live) | set(rebuilt)) - manual_slots)
        if live.get(slot) != rebuilt.get(slot)
    ]


async def repair_inferred_profile(session: AsyncSession, user_id: uuid.UUID) -> list[SlotDrift]:
    """Make live inferred state match the evidence replay (one transaction).

    Manual slots are never touched. Returns the drift that was repaired.
    """
    drifts = await diff_inferred_profile(session, user_id)
    if not drifts:
        return []

    for drift in drifts:
        active = await session.scalar(
            select(UserProfileSlot)
            .where(
                UserProfileSlot.user_id == user_id,
                UserProfileSlot.slot == drift.slot,
                UserProfileSlot.is_active,
                UserProfileSlot.source == "inferred",
            )
            .with_for_update()
        )
        if active is not None:
            active.is_active = False
            await session.flush()
        if drift.rebuilt_value is not None:
            session.add(
                UserProfileSlot(
                    user_id=user_id,
                    slot=drift.slot,
                    value=drift.rebuilt_value,
                    source="inferred",
                )
            )
    await session.flush()
    return drifts
