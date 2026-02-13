"""Schemas for the assistant chat data-stream endpoint."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class LanguageModelMessage(BaseModel):
    """Message shape received from assistant-ui data stream runtime."""

    role: Literal["system", "user", "assistant", "tool"]
    content: Any


class ChatRequest(BaseModel):
    """Request schema for data-stream runtime chat endpoint."""

    messages: list[LanguageModelMessage] = Field(
        default_factory=list,
        description="Conversation history + latest user message",
    )
    system: str | None = Field(default=None, description="Optional system message")
    tools: list[dict[str, Any]] | dict[str, Any] | None = Field(default=None)
    runConfig: dict[str, Any] | None = Field(default=None)
    state: dict[str, Any] | None = Field(default=None)

    # Model context from assistant-ui runtime
    modelName: str | None = Field(default=None, description="Model override from model context")
    model: str | None = Field(default=None, description="Fallback model override key")

    # Optional domain context fields
    context_type: Literal["book", "video", "course"] | None = Field(
        None, description="Type of resource providing context"
    )
    context_id: UUID | None = Field(None, description="ID of the context resource")
    context_meta: dict[str, Any] | None = Field(
        None, description="Additional context metadata (page number, timestamp, etc.)"
    )
    pending_quote: str | None = Field(default=None, description="Optional one-time quoted selection to prefix")
