"""Profile-memory maintenance pass.

Application code defers a job (same transaction as the user-turn write); the
worker replays unprocessed user turns from conversation history, asks the
maintenance model for slot operations, and commits them deterministically
through :mod:`src.memory.service`. The per-user watermark plus the queueing
lock make redelivery idempotent; the LLM only proposes, app code commits.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Literal, cast


if TYPE_CHECKING:
    from src.ai.assistant.models import AssistantConversationHistoryItem
    from src.memory.models import UserProfileSlot

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.jobs import QUEUE_MEMORY, defer_job, memory_queueing_lock
from src.memory.models import UserMemoryWatermark
from src.memory.prompts import MAINTENANCE_SYSTEM_PROMPT
from src.memory.service import SlotEvidence, clear_slot, get_active_slots, record_skip_event, set_slot
from src.memory.slots import is_known_slot


logger = logging.getLogger(__name__)

PROFILE_MAINTENANCE_TASK_NAME = "memory.run_profile_maintenance"

_BATCH_LIMIT = 10
_CONTEXT_TURNS = 2
_CONFIDENCE_FLOOR = 0.6
_MAX_VALUE_LENGTH = 80


class SlotAction(BaseModel):
    """One proposed slot operation from the maintenance model.

    All fields are required so weaker models cannot silently skip them;
    inapplicable fields carry empty strings (e.g. for ignore actions).
    """

    op: Literal["set", "clear", "ignore", "defer"]
    slot: str = Field(description="Slot name from the vocabulary; empty string only for ignore.")
    value: str = Field(
        description="New slot value: a short reusable phrase of at most a few words, e.g. 'text-first'. Never a sentence, never a quote, never the evidence. Empty for clear/ignore/defer.",
    )
    confidence: float = Field(
        ge=0,
        le=1,
        description="0-1 certainty that this is a durable, correctly attributed preference.",
    )
    evidence_text: str = Field(
        description="Dual-trace provenance: short verbatim quote plus one-line scene trace with the absolute date.",
    )
    reason: str = Field(description="One short clause explaining the decision.")


class MaintenanceDecision(BaseModel):
    """Structured output schema for one evaluated user turn."""

    actions: list[SlotAction] = Field(default_factory=list)


@dataclass(slots=True)
class UserTurn:
    """A persisted user message eligible for memory evaluation."""

    message_id: str
    text: str
    created_at: datetime
    prior_user_texts: list[str] = field(default_factory=list)


async def defer_profile_maintenance(session: AsyncSession, *, user_id: uuid.UUID) -> int | None:
    """Enqueue maintenance for a user inside the caller's transaction."""
    return await defer_job(
        session,
        task_name=PROFILE_MAINTENANCE_TASK_NAME,
        queue=QUEUE_MEMORY,
        args={"user_id": str(user_id)},
        queueing_lock=memory_queueing_lock(user_id),
    )


async def process_user_memory(user_id: uuid.UUID) -> int:
    """Evaluate unprocessed user turns; returns how many turns were evaluated.

    All canonical commits, evidence events, and the watermark advance happen in
    one transaction, so retries after a crash are exactly-once.
    """
    from src.database.session import async_session_maker

    async with async_session_maker() as session:
        if not await _user_is_active(session, user_id):
            return 0

        watermark = await _lock_watermark(session, user_id)
        items = await _load_unprocessed_items(session, user_id, after_seq=watermark.last_processed_seq)
        if not items:
            return 0

        turns = _extract_user_turns(items)
        for turn in turns:
            current_profile = await get_active_slots(session, user_id)
            decision = await _propose_actions(user_id=user_id, turn=turn, current_profile=current_profile)
            await _apply_decision(session, user_id=user_id, turn=turn, decision=decision)

        watermark.last_processed_seq = max(item.seq for item in items)
        await session.commit()
        return len(turns)


async def advance_watermark_past_history(session: AsyncSession, *, user_id: uuid.UUID) -> None:
    """Explicit-forget barrier: mark every existing turn as already evaluated.

    Runs in the caller's forget transaction so a still-pending maintenance job
    can never re-extract pre-forget history. Monotonic via GREATEST; serialized
    against running jobs by the watermark row lock.
    """
    from sqlalchemy import text

    await session.execute(
        text(
            """
            INSERT INTO user_memory_watermarks (user_id, last_processed_seq)
            VALUES (
                :user_id,
                COALESCE(
                    (
                        SELECT MAX(items.seq)
                        FROM assistant_conversation_history_items AS items
                        JOIN assistant_conversations AS conversations
                          ON conversations.id = items.conversation_id
                        WHERE conversations.user_id = :user_id
                    ),
                    0
                )
            )
            ON CONFLICT (user_id) DO UPDATE
            SET last_processed_seq = GREATEST(user_memory_watermarks.last_processed_seq, EXCLUDED.last_processed_seq),
                updated_at = NOW()
            """
        ),
        {"user_id": user_id},
    )


async def _user_is_active(session: AsyncSession, user_id: uuid.UUID) -> bool:
    """Queued work can outlive the account that created it; recheck before writing."""
    from src.user.models import User

    return bool(await session.scalar(select(User.is_active).where(User.id == user_id)))


async def _lock_watermark(session: AsyncSession, user_id: uuid.UUID) -> UserMemoryWatermark:
    from sqlalchemy import text

    # Race-free get-or-create: a concurrent forget may be inserting the same
    # row; DO NOTHING + re-select FOR UPDATE blocks instead of erroring.
    await session.execute(
        text("INSERT INTO user_memory_watermarks (user_id) VALUES (:user_id) ON CONFLICT (user_id) DO NOTHING"),
        {"user_id": user_id},
    )
    stmt = select(UserMemoryWatermark).where(UserMemoryWatermark.user_id == user_id).with_for_update()
    watermark = await session.scalar(stmt)
    if watermark is None:  # pragma: no cover - row guaranteed by the upsert
        msg = f"watermark row missing for user {user_id}"
        raise RuntimeError(msg)
    return watermark


async def _load_unprocessed_items(
    session: AsyncSession, user_id: uuid.UUID, *, after_seq: int
) -> list[AssistantConversationHistoryItem]:
    """Newest unprocessed items first, bounded.

    Taking the newest ``_BATCH_LIMIT`` items (then restoring order) keeps each
    job's LLM work bounded and biases toward fresh evidence; anything older
    that the bound skips is rebuild-job territory, not hot-path work.
    """
    from src.ai.assistant.models import AssistantConversation, AssistantConversationHistoryItem

    stmt = (
        select(AssistantConversationHistoryItem)
        .join(
            AssistantConversation,
            AssistantConversationHistoryItem.conversation_id == AssistantConversation.id,
        )
        .where(
            AssistantConversation.user_id == user_id,
            AssistantConversationHistoryItem.seq > after_seq,
        )
        .order_by(AssistantConversationHistoryItem.seq.desc())
        .limit(_BATCH_LIMIT)
    )
    newest_first = list(await session.scalars(stmt))
    return list(reversed(newest_first))


def _extract_user_turns(items: list[AssistantConversationHistoryItem]) -> list[UserTurn]:
    """User-role turns only; assistant text and tool output never feed memory."""
    turns: list[UserTurn] = []
    user_texts_by_conversation: dict[object, list[str]] = {}

    for item in items:
        message = item.message_json
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        text = _message_text(message)
        if not text:
            continue
        prior = user_texts_by_conversation.setdefault(item.conversation_id, [])
        turns.append(
            UserTurn(
                message_id=item.aui_message_id,
                text=text,
                created_at=item.created_at,
                prior_user_texts=prior[-_CONTEXT_TURNS:],
            )
        )
        prior.append(text)

    return turns


def _message_text(message: Mapping[str, object]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for raw_part in content:
        if not isinstance(raw_part, dict):
            continue
        part = cast("Mapping[str, object]", raw_part)
        if part.get("type") != "text":
            continue
        text_value = part.get("text")
        if isinstance(text_value, str) and text_value:
            parts.append(text_value)
    return "\n".join(parts).strip()


async def _propose_actions(
    *,
    user_id: uuid.UUID,
    turn: UserTurn,
    current_profile: list[UserProfileSlot],
) -> MaintenanceDecision:
    """Thin wrapper over the shared LLM runtime; the model only proposes."""
    from src.ai.client import LLMClient
    from src.config.settings import get_settings

    settings = get_settings()
    model = settings.MEMORY_LLM_MODEL.strip() or None

    payload: dict[str, object] = {
        "newest_user_message": turn.text,
        "message_date": str(turn.created_at),
        "prior_user_messages_for_reference_only": turn.prior_user_texts,
        "current_profile_values": {slot.slot: slot.value for slot in current_profile},
    }

    client = LLMClient(agent_id="memory-maintenance")
    result = await client.get_completion(
        [
            {"role": "system", "content": MAINTENANCE_SYSTEM_PROMPT},
            {"role": "user", "content": _to_json(payload)},
        ],
        response_model=MaintenanceDecision,
        user_id=user_id,
        model=model,
        enable_memory=False,
        enable_tools=False,
    )
    if not isinstance(result, MaintenanceDecision):
        msg = "Expected MaintenanceDecision from maintenance structured output"
        raise TypeError(msg)
    return result


def _to_json(payload: dict[str, object]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, default=str)


def resolve_effective_op(action: SlotAction) -> Literal["set", "clear", "ignore", "defer", "drop"]:
    """Deterministic gate between what the model proposed and what may commit.

    The model only proposes; these rules own the final decision:
    - unknown slots are dropped outright
    - low-confidence sets become defers (abstention beats confident misuse)
    - rambling values (model conflating value with evidence) become defers
    """
    if action.op == "ignore" and not action.slot:
        return "ignore"
    if not is_known_slot(action.slot):
        return "drop"
    if action.op != "set":
        return action.op
    value = action.value.strip()
    if not value or action.confidence < _CONFIDENCE_FLOOR or len(value) > _MAX_VALUE_LENGTH:
        return "defer"
    return "set"


async def _apply_decision(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    turn: UserTurn,
    decision: MaintenanceDecision,
) -> None:
    for action in decision.actions:
        effective_op = resolve_effective_op(action)
        if effective_op in {"ignore", "drop"}:
            if effective_op == "drop":
                logger.info("memory.maintenance.unknown_slot", extra={"slot": action.slot, "op": action.op})
            continue

        evidence = SlotEvidence(
            evidence_text=action.evidence_text or None,
            message_id=turn.message_id,
            source_message_created_at=turn.created_at,
            confidence=action.confidence,
        )

        if effective_op == "set":
            result = await set_slot(
                session, user_id=user_id, slot=action.slot, value=action.value, source="inferred", evidence=evidence
            )
        elif effective_op == "clear":
            result = await clear_slot(session, user_id=user_id, slot=action.slot, source="inferred", evidence=evidence)
        else:
            result = await record_skip_event(session, user_id=user_id, slot=action.slot, op="defer", evidence=evidence)

        logger.info(
            "memory.maintenance.action",
            extra={"slot": action.slot, "memory_op": action.op, "commit_status": result.status},
        )
