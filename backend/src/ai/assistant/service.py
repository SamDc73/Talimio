"""Simple assistant service with streaming support."""

import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai import AGENT_ID_ASSISTANT
from src.ai.client import LLMClient
from src.ai.errors import AIRuntimeError
from src.ai.prompts import ASSISTANT_CHAT_SYSTEM_PROMPT
from src.exceptions import DomainError
from src.learning_capabilities.facade import LearningCapabilitiesFacade
from src.learning_capabilities.schemas import BuildContextBundleCapabilityInput

from . import conversations_service
from .schemas import ChatRequest


logger = logging.getLogger(__name__)

ASSISTANT_MAX_USER_MESSAGE_LENGTH = 8_000
ASSISTANT_MAX_HISTORY_MESSAGES = 40
ASSISTANT_REQUIRE_THREAD_ID = True
ASSISTANT_PUBLIC_ERROR_TEXT = "Sorry, I'm having trouble responding right now. Please try again."


class NormalizedChatRequest(BaseModel):
    """Assistant request normalized from assistant-ui data stream payload."""

    latest_user_text: str = Field(default="")
    latest_user_blocks: list[dict[str, Any]] = Field(default_factory=list)
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)
    model: str | None = None
    thread_id: uuid.UUID
    context_type: Literal["book", "video", "course"] | None = None
    context_id: uuid.UUID | None = None
    context_meta: dict[str, Any] | None = None

    model_config = ConfigDict(frozen=True)


def _sse_event(payload: dict[str, Any] | str) -> str:
    """Return a single SSE event line block."""
    encoded = payload if isinstance(payload, str) else json.dumps(payload)
    return f"data: {encoded}\n\n"


def _extract_message_text(content: Any) -> str:
    """Extract plain text from AI SDK-style message content parts."""
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""

    text_parts: list[str] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        part_type = part.get("type")
        if part_type == "text" and isinstance(part.get("text"), str):
            normalized = part["text"].strip()
            if normalized:
                text_parts.append(normalized)

    return " ".join(text_parts).replace("\n", " ").replace("\t", " ").strip()


def _is_image_file_part(media_type: Any, data_url: str) -> bool:
    if isinstance(media_type, str) and media_type.startswith("image/"):
        return True
    return data_url.startswith("data:image/")


def _convert_user_content_to_openai_blocks(content: Any) -> list[dict[str, Any]]:
    if isinstance(content, str):
        normalized = content.strip()
        if not normalized:
            return []
        return [{"type": "text", "text": normalized}]

    if not isinstance(content, list):
        return []

    blocks: list[dict[str, Any]] = []
    for part in content:
        if not isinstance(part, dict):
            continue

        part_type = part.get("type")
        if part_type == "text":
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                blocks.append({"type": "text", "text": text})
            continue

        if part_type == "file":
            data = part.get("data")
            if not isinstance(data, str) or not data.strip():
                continue

            media_type = part.get("mediaType")
            if not isinstance(media_type, str) or not media_type.strip():
                media_type = part.get("mimeType")

            if not _is_image_file_part(media_type, data):
                continue

            blocks.append({"type": "image_url", "image_url": {"url": data}})

    return blocks


def _normalize_chat_request(request: ChatRequest) -> NormalizedChatRequest:
    """Normalize assistant-ui runtime request body into assistant domain request."""
    if ASSISTANT_REQUIRE_THREAD_ID and request.thread_id is None:
        msg = "threadId is required"
        raise ValueError(msg)

    normalized_messages: list[dict[str, Any]] = []
    latest_user_blocks: list[dict[str, Any]] = []
    latest_user_text = ""
    last_user_index = -1

    for item in request.messages:
        if item.role not in {"user", "assistant"}:
            continue

        if item.role == "assistant":
            text = _extract_message_text(item.content)
            if not text:
                continue
            normalized_messages.append({"role": "assistant", "content": text})
            continue

        blocks = _convert_user_content_to_openai_blocks(item.content)
        if not blocks:
            continue

        latest_user_text = _extract_message_text(item.content)
        latest_user_blocks = blocks
        normalized_messages.append({"role": "user", "content": blocks})
        last_user_index = len(normalized_messages) - 1

    if last_user_index < 0 or not latest_user_blocks:
        msg = "Latest user message is required"
        raise ValueError(msg)

    if latest_user_text and len(latest_user_text) > ASSISTANT_MAX_USER_MESSAGE_LENGTH:
        msg = f"Latest user message exceeds max length of {ASSISTANT_MAX_USER_MESSAGE_LENGTH} characters"
        raise ValueError(msg)

    pending_quote = request.pending_quote.strip() if request.pending_quote else ""
    if pending_quote:
        latest_user_blocks = [{"type": "text", "text": f"{pending_quote}\n\n"}, *latest_user_blocks]
        latest_user_text = f"{pending_quote}\n\n{latest_user_text}" if latest_user_text else pending_quote

    history_start_index = max(last_user_index - ASSISTANT_MAX_HISTORY_MESSAGES, 0)

    return NormalizedChatRequest(
        latest_user_text=latest_user_text,
        latest_user_blocks=latest_user_blocks,
        conversation_history=normalized_messages[history_start_index:last_user_index],
        model=request.model_name or request.model,
        thread_id=request.thread_id,
        context_type=request.context_type,
        context_id=request.context_id,
        context_meta=request.context_meta,
    )


def _build_thread_message_payload(message: Any) -> dict[str, Any]:
    payload = message.model_dump(by_alias=True, exclude_none=True, mode="json")
    message_id = payload.get("id")
    if not isinstance(message_id, str) or not message_id.strip():
        payload["id"] = str(uuid.uuid4())
    created_at = payload.get("createdAt")
    if not isinstance(created_at, str) or not created_at.strip():
        payload["createdAt"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return payload


def _extract_latest_user_history_item(request: ChatRequest) -> tuple[dict[str, Any] | None, str | None]:
    last_user_index = -1
    for index in range(len(request.messages) - 1, -1, -1):
        if request.messages[index].role == "user":
            last_user_index = index
            break
    if last_user_index < 0:
        return None, None

    parent_id: str | None = None
    for index in range(last_user_index - 1, -1, -1):
        candidate_id = request.messages[index].id
        if isinstance(candidate_id, str) and candidate_id.strip():
            parent_id = candidate_id
            break

    return _build_thread_message_payload(request.messages[last_user_index]), parent_id


async def assistant_chat(
    request: ChatRequest,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> AsyncGenerator[str]:
    """Stream chat responses with optional context using ui-message-stream protocol."""
    message_id = str(uuid.uuid4())
    normalized_request: NormalizedChatRequest | None = None
    latest_user_message_id: str | None = None
    try:
        # Emit start immediately so the client can render streaming state while prep runs.
        yield _sse_event({"type": "start", "messageId": message_id})

        normalized_request = _normalize_chat_request(request)
        await conversations_service.assert_conversation_ownership(
            session=session,
            user_id=user_id,
            conversation_id=normalized_request.thread_id,
        )

        latest_user_message, latest_user_parent_id = _extract_latest_user_history_item(request)
        if latest_user_message is not None:
            await conversations_service.append_assistant_conversation_history_item(
                session=session,
                user_id=user_id,
                conversation_id=normalized_request.thread_id,
                message=latest_user_message,
                parent_id=latest_user_parent_id,
                run_config=request.run_config,
            )
            raw_user_message_id = latest_user_message.get("id")
            if isinstance(raw_user_message_id, str) and raw_user_message_id.strip():
                latest_user_message_id = raw_user_message_id

        # Build messages with context if available
        messages = await _build_messages(normalized_request, user_id, session)

        # Run completion through shared LLM client so memories and MCP tools are available
        llm_client = LLMClient(agent_id=AGENT_ID_ASSISTANT)
        stream = await llm_client.get_completion(
            messages=messages,
            user_id=user_id,
            model=normalized_request.model,
            stream=True,
        )

        saw_any_content = False

        async for delta in stream:
            if not delta:
                continue
            saw_any_content = True
            yield _sse_event({"type": "text-delta", "textDelta": delta})

        if not saw_any_content:
            logger.warning("Assistant returned empty streamed response for user %s", user_id)
            fallback_content = "I couldn't retrieve results right now. Please try again."
            yield _sse_event({"type": "text-delta", "textDelta": fallback_content})

        yield _sse_event(
            {
                "type": "finish",
                "finishReason": "stop",
                "usage": {"promptTokens": 0, "completionTokens": 0},
            }
        )
        yield _sse_event("[DONE]")

    except (ValueError, DomainError) as error:
        logger.warning("Chat validation failed for user %s: %s", user_id, error)
        yield _sse_event({"type": "error", "errorText": ASSISTANT_PUBLIC_ERROR_TEXT})
        yield _sse_event(
            {
                "type": "finish",
                "finishReason": "error",
                "usage": {"promptTokens": 0, "completionTokens": 0},
            }
        )
        yield _sse_event("[DONE]")
    except (AIRuntimeError, RuntimeError, TypeError, OSError, SQLAlchemyError) as error:
        if isinstance(error, AIRuntimeError):
            logger.warning(
                "LLM runtime failure for user %s: %s (%s)",
                user_id,
                error,
                error.category.value,
            )
        else:
            logger.exception("Chat failed for user %s", user_id)
        if normalized_request and latest_user_message_id:
            incomplete_message = {
                "id": str(uuid.uuid4()),
                "role": "assistant",
                "createdAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "content": [],
                "status": {"type": "incomplete", "reason": "error"},
            }
            try:
                await conversations_service.append_assistant_conversation_history_item(
                    session=session,
                    user_id=user_id,
                    conversation_id=normalized_request.thread_id,
                    message=incomplete_message,
                    parent_id=latest_user_message_id,
                    run_config=request.run_config,
                )
            except (RuntimeError, TypeError, ValueError, OSError, SQLAlchemyError, DomainError):
                logger.exception(
                    "Failed to persist incomplete assistant message for thread %s",
                    normalized_request.thread_id,
                )
        yield _sse_event({"type": "error", "errorText": ASSISTANT_PUBLIC_ERROR_TEXT})
        yield _sse_event(
            {
                "type": "finish",
                "finishReason": "error",
                "usage": {"promptTokens": 0, "completionTokens": 0},
            }
        )
        yield _sse_event("[DONE]")


async def _build_messages(
    request: NormalizedChatRequest,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> list[dict[str, Any]]:
    """Build message list with capability-backed context packet injection."""
    learning_facade = LearningCapabilitiesFacade(session)
    context_bundle = await learning_facade.build_context_bundle(
        user_id=user_id,
        payload=BuildContextBundleCapabilityInput(
            context_type=request.context_type,
            context_id=request.context_id,
            context_meta=request.context_meta or {},
            latest_user_text=request.latest_user_text,
            selected_quote=None,
        ),
    )
    logger.info(
        "learning_capability.context_bundle.injected",
        extra={
            "user_id": str(user_id),
            "context_type": context_bundle.context_type,
            "has_course_state": context_bundle.course_state is not None,
            "has_lesson_state": context_bundle.lesson_state is not None,
            "has_frontier_state": context_bundle.frontier_state is not None,
            "relevant_course_count": len(context_bundle.relevant_courses),
        },
    )

    messages: list[dict[str, Any]] = [{"role": "system", "content": ASSISTANT_CHAT_SYSTEM_PROMPT}]
    messages.extend(request.conversation_history)

    user_blocks = list(request.latest_user_blocks)
    context_packet = context_bundle.model_dump_json(by_alias=True, exclude_none=True)
    user_blocks.append({"type": "text", "text": f"\n\n[learning_context_packet]\n{context_packet}"})

    messages.append({"role": "user", "content": user_blocks})
    return messages
