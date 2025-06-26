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
