"""Schemas for the assistant chat data-stream endpoint."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LanguageModelMessage(BaseModel):
    """Message shape received from assistant-ui data stream runtime."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str | None = None
    role: Literal["system", "user", "assistant", "tool"]
    content: Any
    created_at: str | None = Field(default=None, alias="createdAt")


class ChatRequest(BaseModel):
    """Request schema for data-stream runtime chat endpoint."""

    model_config = ConfigDict(populate_by_name=True)

    messages: list[LanguageModelMessage] = Field(
        default_factory=list,
        description="Conversation history + latest user message",
    )
    system: str | None = Field(default=None, description="Optional system message")
    tools: list[dict[str, Any]] | dict[str, Any] | None = Field(default=None)
    run_config: dict[str, Any] | None = Field(default=None, alias="runConfig")
    state: dict[str, Any] | None = Field(default=None)

    # Model context from assistant-ui runtime
    model_name: str | None = Field(default=None, alias="modelName", description="Model override from model context")
    model: str | None = Field(default=None, description="Fallback model override key")
    thread_id: uuid.UUID | None = Field(default=None, alias="threadId", description="Conversation thread identifier")

    # Optional domain context fields
    context_type: Literal["book", "video", "course"] | None = Field(
        None, alias="contextType", description="Type of resource providing context"
    )
    context_id: uuid.UUID | None = Field(None, alias="contextId", description="ID of the context resource")
    context_meta: dict[str, Any] | None = Field(
        None, alias="contextMeta", description="Additional context metadata (page number, timestamp, etc.)"
    )
    pending_quote: str | None = Field(
        default=None, alias="pendingQuote", description="Optional one-time quoted selection to prefix"
    )


class CreateConversationRequest(BaseModel):
    """Create a new assistant conversation."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    title: str | None = Field(default=None, max_length=200)
    context_type: Literal["book", "video", "course"] | None = Field(default=None, alias="contextType")
    context_id: uuid.UUID | None = Field(default=None, alias="contextId")
    context_meta: dict[str, Any] | None = Field(default=None, alias="contextMeta")


class CreateConversationResponse(BaseModel):
    """Conversation id response for assistant-ui thread initialization."""

    model_config = ConfigDict(populate_by_name=True)

    remote_id: uuid.UUID = Field(alias="remoteId")


class RenameConversationRequest(BaseModel):
    """Rename request for an assistant conversation."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    title: str | None = Field(default=None, max_length=200)


class ConversationThreadResponse(BaseModel):
    """Single assistant conversation metadata response."""

    model_config = ConfigDict(populate_by_name=True)

    remote_id: uuid.UUID = Field(alias="remoteId")
    external_id: str | None = Field(default=None, alias="externalId")
    status: Literal["regular", "archived"]
    title: str | None = None
    context_type: Literal["book", "video", "course"] | None = Field(default=None, alias="contextType")
    context_id: uuid.UUID | None = Field(default=None, alias="contextId")
    context_meta: dict[str, Any] = Field(default_factory=dict, alias="contextMeta")
    head_message_id: str | None = Field(default=None, alias="headMessageId")
    last_message_preview: str | None = Field(default=None, alias="lastMessagePreview")
    message_count: int = Field(default=0, alias="messageCount")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class ConversationListResponse(BaseModel):
    """Paginated assistant conversation list response."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[ConversationThreadResponse]
    page: int
    limit: int
    total: int


class ConversationHistoryItemRequest(BaseModel):
    """Append payload item for assistant-ui thread history adapter."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    message: dict[str, Any]
    parent_id: str | None = Field(default=None, alias="parentId")
    run_config: dict[str, Any] | None = Field(default=None, alias="runConfig")

    @field_validator("message")
    @classmethod
    def _require_message_id(cls, value: dict[str, Any]) -> dict[str, Any]:
        message_id = value.get("id")
        if isinstance(message_id, str) and message_id.strip():
            return value
        msg = "message.id is required and must be a non-empty string"
        raise ValueError(msg)


class ConversationHistoryItemResponse(BaseModel):
    """History item response in assistant-ui exported repository format."""

    model_config = ConfigDict(populate_by_name=True)

    message: dict[str, Any]
    parent_id: str | None = Field(default=None, alias="parentId")
    run_config: dict[str, Any] | None = Field(default=None, alias="runConfig")


class ConversationHistoryResponse(BaseModel):
    """Assistant-ui exported message repository payload."""

    model_config = ConfigDict(populate_by_name=True)

    head_id: str | None = Field(default=None, alias="headId")
    messages: list[ConversationHistoryItemResponse]


class AppendConversationHistoryResponse(BaseModel):
    """History append result payload."""

    model_config = ConfigDict(populate_by_name=True)

    appended: bool
    head_id: str | None = Field(default=None, alias="headId")
