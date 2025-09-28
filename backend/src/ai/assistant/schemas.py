"""Schemas for the assistant module - dead simple."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Simple chat message."""

    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    """Request schema for chat endpoint."""

    message: str = Field(..., min_length=1, description="User message to send to assistant")
    conversation_history: list[ChatMessage] = Field(
        default_factory=list,
        description="Previous messages in the conversation",
    )
    stream: bool = Field(default=False, description="Whether to stream the response")
    model: str | None = Field(None, description="Optional model override")

    # Optional context fields
    context_type: Literal["book", "video", "course"] | None = Field(
        None, description="Type of resource providing context"
    )
    context_id: UUID | None = Field(None, description="ID of the context resource")
    context_meta: dict[str, Any] | None = Field(
        None, description="Additional context metadata (page number, timestamp, etc.)"
    )
