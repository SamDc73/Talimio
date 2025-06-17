from uuid import UUID

from pydantic import BaseModel


class ChatMessage(BaseModel):
    """Schema for a chat message."""

    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """Request schema for chat endpoint."""

    message: str
    conversation_history: list[ChatMessage] = []
    user_id: str | None = None


class ChatResponse(BaseModel):
    """Response schema for chat endpoint."""

    response: str
    conversation_id: UUID | None = None
