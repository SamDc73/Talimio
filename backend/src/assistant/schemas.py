from typing import Any, Literal
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
    roadmap_id: str | None = None  # Optional roadmap ID for RAG context
    stream: bool = False  # Enable streaming response
    model: str | None = None  # Optional model ID to use for the request

    # Phase 2: Context-aware fields
    context_type: Literal["book", "video", "course"] | None = None
    context_id: UUID | None = None
    context_meta: dict[str, Any] | None = None  # position info like page, timestamp, lesson_id


class Citation(BaseModel):
    """Schema for document citation."""

    document_id: int
    document_title: str
    similarity_score: float


class ChatResponse(BaseModel):
    """Response schema for chat endpoint."""

    response: str
    conversation_id: UUID | None = None
    citations: list[Citation] = []  # Citations from RAG documents
    context_source: str | None = None  # Source of context used (e.g., "PDF page 5", "Video 02:15-03:45")
