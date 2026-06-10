"""Deterministic commit logic for canonical user profile memory.

LLM passes only *propose* slot operations; this module owns validation and the
final commit. Merge rules:

- same slot + same value      -> no-op (evidence freshness still advances)
- same slot + different value -> supersede the active row
- clear                       -> deactivate the active row
- stale evidence              -> rejected (older than ``last_evidence_at``)
- manual beats inferred       -> inferred writes never override manual values
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.models import UserProfileSlot, UserProfileSlotEvent
from src.memory.slots import is_known_slot


SlotSource = Literal["manual", "inferred", "legacy_migration"]
CommitStatus = Literal["applied", "noop", "rejected_stale", "rejected_manual"]


@dataclass(frozen=True, slots=True)
class SlotCommitResult:
    """Outcome of one deterministic slot commit."""

    slot: str
    status: CommitStatus


@dataclass(frozen=True, slots=True)
class SlotEvidence:
    """Provenance carried by an inferred slot proposal."""

    evidence_text: str | None = None
    message_id: str | None = None
    source_message_created_at: datetime | None = None
    confidence: float | None = None


async def get_active_slots(session: AsyncSession, user_id: uuid.UUID) -> list[UserProfileSlot]:
    """Return the user's active profile slots ordered by slot name."""
    stmt = (
        select(UserProfileSlot)
        .where(UserProfileSlot.user_id == user_id, UserProfileSlot.is_active)
        .order_by(UserProfileSlot.slot)
    )
    return list(await session.scalars(stmt))


def build_profile_block(slots: list[UserProfileSlot]) -> str:
    """Render active slots as a compact human-readable block ('' when empty)."""
    return "\n".join(f"- {slot.slot}: {slot.value}" for slot in slots)


async def get_custom_instructions(session: AsyncSession, user_id: uuid.UUID) -> str:
    """Return the user's raw custom-instructions text ('' when unset)."""
    from src.user.models import UserPreferences

    preferences = await session.get(UserPreferences, user_id)
    if preferences is None:
        return ""
    nested = preferences.preferences.get("user_preferences")
    raw = nested.get("custom_instructions") if isinstance(nested, dict) else None
    return raw.strip() if isinstance(raw, str) else ""


async def build_memory_context(session: AsyncSession, user_id: uuid.UUID) -> str:
    """One merged profile context: custom instructions (verbatim) plus active slots.

    This is the single durable-memory block prompts receive; custom instructions
    and profile slots are never injected as parallel sources.
    """
    parts: list[str] = []
    instructions = await get_custom_instructions(session, user_id)
    if instructions:
        parts.append(f"User custom instructions:\n{instructions}")
    profile_block = build_profile_block(await get_active_slots(session, user_id))
    if profile_block:
        parts.append(f"User profile (durable preferences):\n{profile_block}")
    return "\n\n".join(parts)


async def set_slot(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    slot: str,
    value: str,
    source: SlotSource,
    evidence: SlotEvidence | None = None,
) -> SlotCommitResult:
    """Set a slot value under row-level locking, applying the merge rules."""
    _validate_slot(slot)
    value = value.strip()
    if not value:
        msg = "slot value must be non-empty; use clear_slot to remove a value"
        raise ValueError(msg)

    evidence = evidence or SlotEvidence()
    active = await _lock_active_slot(session, user_id=user_id, slot=slot)
    status = _decide_set_status(active, value=value, source=source, evidence=evidence)

    if status == "applied":
        evidence_at = evidence.source_message_created_at or datetime.now(UTC)
        if active is not None:
            active.is_active = False
            await session.flush()
        session.add(
            UserProfileSlot(user_id=user_id, slot=slot, value=value, source=source, last_evidence_at=evidence_at)
        )
    elif status == "noop" and active is not None:
        _advance_evidence_freshness(active, evidence.source_message_created_at)

    _record_event(
        session,
        user_id=user_id,
        slot=slot,
        op="set",
        proposed_value=value,
        source=source,
        evidence=evidence,
        status=status,
    )
    await session.flush()
    return SlotCommitResult(slot=slot, status=status)


async def clear_slot(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    slot: str,
    source: SlotSource,
    evidence: SlotEvidence | None = None,
) -> SlotCommitResult:
    """Deactivate a slot's active value under row-level locking."""
    _validate_slot(slot)
    evidence = evidence or SlotEvidence()
    active = await _lock_active_slot(session, user_id=user_id, slot=slot)

    if active is None:
        status: CommitStatus = "noop"
    elif source == "inferred" and active.source == "manual":
        status = "rejected_manual"
    elif _is_stale(active, source=source, evidence=evidence):
        status = "rejected_stale"
    else:
        active.is_active = False
        status = "applied"

    _record_event(
        session,
        user_id=user_id,
        slot=slot,
        op="clear",
        proposed_value=None,
        source=source,
        evidence=evidence,
        status=status,
    )
    await session.flush()
    return SlotCommitResult(slot=slot, status=status)


async def redact_slot_evidence(session: AsyncSession, *, user_id: uuid.UUID, slot: str | None = None) -> int:
    """Tombstone raw evidence on explicit user-forget (slot-scoped or all).

    Keeps the structural record (slot, op, status, timestamps) for replay
    safety and drift checks; the text and proposed value are gone, so rebuilds
    can never resurrect the forgotten state.
    """
    stmt = (
        update(UserProfileSlotEvent)
        .where(UserProfileSlotEvent.user_id == user_id, UserProfileSlotEvent.redacted_at.is_(None))
        .values(evidence_text=None, proposed_value=None, redacted_at=datetime.now(UTC))
    )
    if slot is not None:
        stmt = stmt.where(UserProfileSlotEvent.slot == slot)
    result = await session.execute(stmt)
    return getattr(result, "rowcount", 0) or 0


async def record_skip_event(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    slot: str,
    op: Literal["ignore", "defer"],
    evidence: SlotEvidence | None = None,
) -> SlotCommitResult:
    """Log an ignore/defer decision for audit without touching canonical state."""
    _validate_slot(slot)
    _record_event(
        session,
        user_id=user_id,
        slot=slot,
        op=op,
        proposed_value=None,
        source="inferred",
        evidence=evidence or SlotEvidence(),
        status="noop",
    )
    await session.flush()
    return SlotCommitResult(slot=slot, status="noop")


def _validate_slot(slot: str) -> None:
    if not is_known_slot(slot):
        msg = f"unknown profile slot: {slot!r}"
        raise ValueError(msg)


async def _lock_active_slot(session: AsyncSession, *, user_id: uuid.UUID, slot: str) -> UserProfileSlot | None:
    stmt = (
        select(UserProfileSlot)
        .where(UserProfileSlot.user_id == user_id, UserProfileSlot.slot == slot, UserProfileSlot.is_active)
        .with_for_update()
    )
    return await session.scalar(stmt)


def _decide_set_status(
    active: UserProfileSlot | None,
    *,
    value: str,
    source: SlotSource,
    evidence: SlotEvidence,
) -> CommitStatus:
    if active is None:
        return "applied"
    if active.value == value:
        return "noop"
    if source == "inferred" and active.source == "manual":
        return "rejected_manual"
    if _is_stale(active, source=source, evidence=evidence):
        return "rejected_stale"
    return "applied"


def _is_stale(active: UserProfileSlot, *, source: SlotSource, evidence: SlotEvidence) -> bool:
    """Older evidence must not overwrite newer canonical state (inferred writes only)."""
    return (
        source == "inferred"
        and evidence.source_message_created_at is not None
        and active.last_evidence_at is not None
        and evidence.source_message_created_at < active.last_evidence_at
    )


def _advance_evidence_freshness(active: UserProfileSlot, evidence_at: datetime | None) -> None:
    if evidence_at is not None and (active.last_evidence_at is None or evidence_at > active.last_evidence_at):
        active.last_evidence_at = evidence_at


def _record_event(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    slot: str,
    op: str,
    proposed_value: str | None,
    source: SlotSource,
    evidence: SlotEvidence,
    status: CommitStatus,
) -> None:
    """Log provenance for inferred writes; manual edits are their own provenance."""
    if source != "inferred":
        return
    session.add(
        UserProfileSlotEvent(
            user_id=user_id,
            slot=slot,
            op=op,
            proposed_value=proposed_value,
            confidence=evidence.confidence,
            source=source,
            message_id=evidence.message_id,
            source_message_created_at=evidence.source_message_created_at,
            evidence_text=evidence.evidence_text,
            status=status,
        )
    )
