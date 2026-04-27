import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import NotFoundError, ValidationError

from .models import AssistantConversation, AssistantConversationHistoryItem


DEFAULT_CONVERSATIONS_PAGE_SIZE = 20
MAX_CONVERSATIONS_PAGE_SIZE = 100
CONVERSATION_PREVIEW_LENGTH = 140
CONVERSATION_STATUS_REGULAR = "regular"
CONVERSATION_STATUS_ARCHIVED = "archived"


class AssistantConversationNotFoundError(NotFoundError):
    """Raised when a conversation does not exist for the current user."""

    def __init__(self, message: str = "Conversation not found") -> None:
        super().__init__(message=message, feature_area="assistant")


class AssistantConversationValidationError(ValidationError):
    """Raised when conversation input payload is invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(message, feature_area="assistant")


def _normalize_context_seed(
    context_type: str | None,
    context_id: uuid.UUID | None,
    context_meta: dict[str, Any] | None,
) -> tuple[str | None, uuid.UUID | None, dict[str, Any]]:
    if context_id is not None and context_type is None:
        msg = "contextType is required when contextId is provided"
        raise AssistantConversationValidationError(msg)

    if context_type is not None and context_id is None:
        msg = "contextId is required when contextType is provided"
        raise AssistantConversationValidationError(msg)

    return context_type, context_id, context_meta or {}


def _extract_message_preview(message_json: dict[str, Any]) -> str | None:
    content = message_json.get("content")
    if isinstance(content, str):
        preview = content.strip()
        return preview[:CONVERSATION_PREVIEW_LENGTH] if preview else None

    if not isinstance(content, list):
        return None

    text_parts: list[str] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") != "text":
            continue
        text = part.get("text")
        if isinstance(text, str) and text.strip():
            text_parts.append(text.strip())

    if not text_parts:
        return None

    preview = " ".join(text_parts).strip()
    return preview[:CONVERSATION_PREVIEW_LENGTH] if preview else None


def _parse_message_created_at(message_json: dict[str, Any]) -> datetime:
    raw_value = message_json.get("createdAt")
    if isinstance(raw_value, str) and raw_value:
        normalized = raw_value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return datetime.now(UTC)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    if isinstance(raw_value, (int, float)) and not isinstance(raw_value, bool):
        seconds_value = raw_value / 1000 if raw_value > 1_000_000_000_000 else raw_value
        try:
            return datetime.fromtimestamp(seconds_value, tz=UTC)
        except OverflowError, OSError, ValueError:
            return datetime.now(UTC)

    return datetime.now(UTC)


def _extract_message_id(message_json: dict[str, Any]) -> str:
    raw_message_id = message_json.get("id")
    if isinstance(raw_message_id, str) and raw_message_id.strip():
        return raw_message_id

    msg = "message.id is required and must be a non-empty string"
    raise AssistantConversationValidationError(msg)


def _normalize_history_message_metadata(role: str | None, metadata_value: Any) -> dict[str, Any]:
    metadata = dict(metadata_value) if isinstance(metadata_value, dict) else {}

    custom = metadata.get("custom")
    if not isinstance(custom, dict):
        metadata["custom"] = {}

    if role == "assistant":
        steps = metadata.get("steps")
        if not isinstance(steps, list):
            metadata["steps"] = []

        unstable_annotations = metadata.get("unstable_annotations")
        if not isinstance(unstable_annotations, list):
            metadata["unstable_annotations"] = []

        unstable_data = metadata.get("unstable_data")
        if not isinstance(unstable_data, list):
            metadata["unstable_data"] = []

        if "unstable_state" not in metadata:
            metadata["unstable_state"] = None

    return metadata


def _normalize_history_message_payload(message_json: dict[str, Any]) -> dict[str, Any]:
    normalized_message = dict(message_json)
    role = normalized_message.get("role")
    role_value = role if isinstance(role, str) else None
    normalized_message["metadata"] = _normalize_history_message_metadata(role_value, normalized_message.get("metadata"))
    if role_value == "user" and not isinstance(normalized_message.get("attachments"), list):
        normalized_message["attachments"] = []
    return normalized_message


def _normalize_conversation_title(title: str | None) -> str | None:
    if title is None:
        return None
    normalized = title.strip()
    return normalized or None


def _conversation_to_payload(
    *,
    conversation: AssistantConversation,
    message_count: int,
    last_message_preview: str | None,
) -> dict[str, Any]:
    return {
        "remote_id": conversation.id,
        "external_id": None,
        "status": conversation.status,
        "title": conversation.title,
        "context_type": conversation.context_type,
        "context_id": conversation.context_id,
        "context_meta": conversation.context_meta,
        "head_message_id": conversation.head_message_id,
        "updated_at": conversation.updated_at,
        "created_at": conversation.created_at,
        "message_count": message_count,
        "last_message_preview": last_message_preview,
    }


async def _get_history_count_and_preview(
    *,
    session: AsyncSession,
    conversation_id: uuid.UUID,
) -> tuple[int, str | None]:
    count = int(
        (
            await session.scalar(
                select(func.count(AssistantConversationHistoryItem.id)).where(
                    AssistantConversationHistoryItem.conversation_id == conversation_id
                )
            )
        )
        or 0
    )
    latest_message_json = await session.scalar(
        select(AssistantConversationHistoryItem.message_json)
        .where(AssistantConversationHistoryItem.conversation_id == conversation_id)
        .order_by(AssistantConversationHistoryItem.seq.desc())
        .limit(1)
    )
    preview = _extract_message_preview(latest_message_json if isinstance(latest_message_json, dict) else {})
    return count, preview


async def create_assistant_conversation(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    title: str | None,
    context_type: str | None,
    context_id: uuid.UUID | None,
    context_meta: dict[str, Any] | None,
) -> AssistantConversation:
    """Create a new assistant conversation for the authenticated user."""
    normalized_context_type, normalized_context_id, normalized_context_meta = _normalize_context_seed(
        context_type=context_type,
        context_id=context_id,
        context_meta=context_meta,
    )

    conversation = AssistantConversation(
        user_id=user_id,
        title=_normalize_conversation_title(title),
        status=CONVERSATION_STATUS_REGULAR,
        context_type=normalized_context_type,
        context_id=normalized_context_id,
        context_meta=normalized_context_meta,
    )
    session.add(conversation)
    await session.flush()
    await session.refresh(conversation)
    return conversation


async def get_assistant_conversation(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> AssistantConversation:
    """Fetch one assistant conversation owned by the user."""
    conversation = await session.scalar(
        select(AssistantConversation).where(
            AssistantConversation.id == conversation_id,
            AssistantConversation.user_id == user_id,
        )
    )
    if conversation is None:
        raise AssistantConversationNotFoundError
    return conversation


async def get_assistant_conversation_with_summary(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> dict[str, Any]:
    """Fetch a conversation with preview and message count fields."""
    conversation = await get_assistant_conversation(session=session, user_id=user_id, conversation_id=conversation_id)
    message_count, preview = await _get_history_count_and_preview(session=session, conversation_id=conversation.id)
    return _conversation_to_payload(
        conversation=conversation,
        message_count=message_count,
        last_message_preview=preview,
    )


async def list_assistant_conversations(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    page: int = 1,
    limit: int = DEFAULT_CONVERSATIONS_PAGE_SIZE,
) -> tuple[list[dict[str, Any]], int]:
    """Return paginated assistant conversations ordered by most recent update."""
    normalized_page = max(page, 1)
    normalized_limit = min(max(limit, 1), MAX_CONVERSATIONS_PAGE_SIZE)
    offset_value = (normalized_page - 1) * normalized_limit

    total_stmt = select(func.count(AssistantConversation.id)).where(AssistantConversation.user_id == user_id)
    total = int((await session.scalar(total_stmt)) or 0)

    rows = (
        (
            await session.execute(
                select(AssistantConversation)
                .where(AssistantConversation.user_id == user_id)
                .order_by(AssistantConversation.updated_at.desc())
                .offset(offset_value)
                .limit(normalized_limit)
            )
        )
        .scalars()
        .all()
    )

    if not rows:
        return [], total

    conversation_ids = [conversation.id for conversation in rows]

    count_rows = await session.execute(
        select(
            AssistantConversationHistoryItem.conversation_id,
            func.count(AssistantConversationHistoryItem.id),
        )
        .where(AssistantConversationHistoryItem.conversation_id.in_(conversation_ids))
        .group_by(AssistantConversationHistoryItem.conversation_id)
    )
    message_count_by_conversation = {row[0]: int(row[1]) for row in count_rows.all()}

    latest_rows = await session.execute(
        select(
            AssistantConversationHistoryItem.conversation_id,
            AssistantConversationHistoryItem.message_json,
        )
        .where(AssistantConversationHistoryItem.conversation_id.in_(conversation_ids))
        .order_by(
            AssistantConversationHistoryItem.conversation_id,
            AssistantConversationHistoryItem.seq.desc(),
        )
        .distinct(AssistantConversationHistoryItem.conversation_id)
    )
    preview_by_conversation: dict[uuid.UUID, str | None] = {}
    for row in latest_rows.all():
        preview_by_conversation[row[0]] = _extract_message_preview(row[1] if isinstance(row[1], dict) else {})

    items = [
        _conversation_to_payload(
            conversation=conversation,
            message_count=message_count_by_conversation.get(conversation.id, 0),
            last_message_preview=preview_by_conversation.get(conversation.id),
        )
        for conversation in rows
    ]

    return items, total


async def rename_assistant_conversation(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    title: str | None,
) -> AssistantConversation:
    """Rename a conversation owned by the current user."""
    conversation = await get_assistant_conversation(session=session, user_id=user_id, conversation_id=conversation_id)
    conversation.title = _normalize_conversation_title(title)
    conversation.updated_at = datetime.now(UTC)
    await session.flush()
    await session.refresh(conversation)
    return conversation


async def archive_assistant_conversation(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> AssistantConversation:
    """Set a conversation status to archived."""
    conversation = await get_assistant_conversation(session=session, user_id=user_id, conversation_id=conversation_id)
    conversation.status = CONVERSATION_STATUS_ARCHIVED
    conversation.updated_at = datetime.now(UTC)
    await session.flush()
    await session.refresh(conversation)
    return conversation


async def unarchive_assistant_conversation(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> AssistantConversation:
    """Restore a conversation status back to regular."""
    conversation = await get_assistant_conversation(session=session, user_id=user_id, conversation_id=conversation_id)
    conversation.status = CONVERSATION_STATUS_REGULAR
    conversation.updated_at = datetime.now(UTC)
    await session.flush()
    await session.refresh(conversation)
    return conversation


async def delete_assistant_conversation(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> None:
    """Delete one conversation and cascade-delete its history items."""
    conversation = await get_assistant_conversation(session=session, user_id=user_id, conversation_id=conversation_id)
    await session.delete(conversation)
    await session.flush()


async def load_assistant_conversation_history(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    lock_for_update: bool = False,
) -> dict[str, Any]:
    """Load assistant-ui exported history in stable insertion order."""
    if lock_for_update:
        conversation = await session.scalar(
            select(AssistantConversation)
            .where(
                AssistantConversation.id == conversation_id,
                AssistantConversation.user_id == user_id,
            )
            .with_for_update()
        )
        if conversation is None:
            raise AssistantConversationNotFoundError
    else:
        conversation = await get_assistant_conversation(session=session, user_id=user_id, conversation_id=conversation_id)

    rows = (
        (
            await session.execute(
                select(AssistantConversationHistoryItem)
                .where(AssistantConversationHistoryItem.conversation_id == conversation.id)
                .order_by(AssistantConversationHistoryItem.seq.asc())
            )
        )
        .scalars()
        .all()
    )

    messages = [
        {
            "message": _normalize_history_message_payload(row.message_json),
            "parent_id": row.parent_aui_message_id,
            "run_config": row.run_config,
        }
        for row in rows
    ]

    if conversation.head_message_id:
        head_id = conversation.head_message_id
    elif rows:
        head_id = rows[-1].aui_message_id
    else:
        head_id = None

    return {"head_id": head_id, "messages": messages}


async def append_assistant_conversation_history_item(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    message: dict[str, Any],
    parent_id: str | None,
    run_config: dict[str, Any] | None,
) -> bool:
    """Append one history item and ignore duplicates idempotently."""
    conversation = await get_assistant_conversation(session=session, user_id=user_id, conversation_id=conversation_id)

    normalized_message = _normalize_history_message_payload(message)

    aui_message_id = _extract_message_id(normalized_message)
    created_at = _parse_message_created_at(normalized_message)

    insert_stmt = (
        postgres_insert(AssistantConversationHistoryItem)
        .values(
            conversation_id=conversation.id,
            aui_message_id=aui_message_id,
            parent_aui_message_id=parent_id,
            message_json=normalized_message,
            run_config=run_config,
            created_at=created_at,
        )
        .on_conflict_do_nothing(
            index_elements=[
                AssistantConversationHistoryItem.conversation_id,
                AssistantConversationHistoryItem.aui_message_id,
            ]
        )
        .returning(AssistantConversationHistoryItem.id)
    )
    inserted_id = await session.scalar(insert_stmt)

    if inserted_id is None:
        return False

    conversation.head_message_id = aui_message_id
    conversation.updated_at = datetime.now(UTC)
    await session.flush()
    return True


async def assert_conversation_ownership(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> None:
    """Validate that thread id belongs to the current user."""
    try:
        await get_assistant_conversation(session=session, user_id=user_id, conversation_id=conversation_id)
    except AssistantConversationNotFoundError as error:
        msg = "threadId must reference a conversation owned by the current user"
        raise AssistantConversationValidationError(msg) from error
