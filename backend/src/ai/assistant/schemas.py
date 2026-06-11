"""Schemas for the assistant chat data-stream endpoint."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field, JsonValue, field_validator

from src.config.schema_casing import CamelModel


class LanguageModelMessage(CamelModel):
    """Message shape received from assistant-ui data stream runtime."""

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    role: Literal["system", "user", "assistant", "tool"]
    content: JsonValue
    created_at: str | None = None


class ChatRequest(CamelModel):
    """Request schema for data-stream runtime chat endpoint."""

    messages: list[LanguageModelMessage] = Field(
        default_factory=list,
        description="Conversation history + latest user message",
    )
    system: str | None = Field(default=None, description="Optional system message")
    tools: list[dict[str, JsonValue]] | dict[str, JsonValue] | None = Field(default=None)
    run_config: dict[str, JsonValue] | None = Field(default=None)
    state: dict[str, JsonValue] | None = Field(default=None)

    # Model context from assistant-ui runtime
    model_name: str | None = Field(default=None, description="Model override from model context")
    model: str | None = Field(default=None, description="Fallback model override key")
    thread_id: uuid.UUID | None = Field(default=None, description="Conversation thread identifier")

    # Optional domain context fields
    context_type: Literal["book", "video", "course"] | None = Field(
        None, description="Type of resource providing context"
    )
    context_id: uuid.UUID | None = Field(None, description="ID of the context resource")
    context_meta: dict[str, JsonValue] | None = Field(
        None, description="Additional context metadata (page number, timestamp, etc.)"
    )
    pending_quote: str | None = Field(
        default=None, description="Optional one-time quoted selection to prefix"
    )


class CreateConversationRequest(CamelModel):
    """Create a new assistant conversation."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=200)
    context_type: Literal["book", "video", "course"] | None = None
    context_id: uuid.UUID | None = None
    context_meta: dict[str, JsonValue] | None = None


class CreateConversationResponse(CamelModel):
    """Conversation id response for assistant-ui thread initialization."""

    remote_id: uuid.UUID


class RenameConversationRequest(CamelModel):
    """Rename request for an assistant conversation."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=200)


class ConversationThreadResponse(CamelModel):
    """Single assistant conversation metadata response."""

    remote_id: uuid.UUID
    external_id: str | None = None
    status: Literal["regular", "archived"]
    title: str | None = None
    context_type: Literal["book", "video", "course"] | None = None
    context_id: uuid.UUID | None = None
    context_meta: dict[str, JsonValue] = Field(default_factory=dict)
    head_message_id: str | None = None
    last_message_preview: str | None = None
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(CamelModel):
    """Paginated assistant conversation list response."""

    items: list[ConversationThreadResponse]
    page: int
    limit: int
    total: int


class ConversationHistoryItemRequest(CamelModel):
    """Append payload item for assistant-ui thread history adapter."""

    model_config = ConfigDict(extra="forbid")

    message: dict[str, JsonValue]
    parent_id: str | None = None
    run_config: dict[str, JsonValue] | None = None

    @field_validator("message")
    @classmethod
    def _require_message_id(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        message_id = value.get("id")
        if isinstance(message_id, str) and message_id.strip():
            return value
        msg = "message.id is required and must be a non-empty string"
        raise ValueError(msg)


class ConversationHistoryItemResponse(CamelModel):
    """History item response in assistant-ui exported repository format."""

    message: dict[str, JsonValue]
    parent_id: str | None = None
    run_config: dict[str, JsonValue] | None = None


class ConversationHistoryResponse(CamelModel):
    """Assistant-ui exported message repository payload."""

    head_id: str | None = None
    messages: list[ConversationHistoryItemResponse]


class AppendConversationHistoryResponse(CamelModel):
    """History append result payload."""

    appended: bool
    head_id: str | None = None
