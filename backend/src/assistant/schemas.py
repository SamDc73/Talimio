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
    user_id: UUID | None = None
    roadmap_id: str | None = None  # Optional roadmap ID for RAG context
    stream: bool = False  # Enable streaming response
    model: str | None = None  # Optional model ID to use for the request

    # Context-aware fields
    context_type: Literal["book", "video", "course"] | None = None
    context_id: UUID | None = None
    context_meta: dict[str, Any] | None = None  # position info like page, timestamp, lesson_id


class Citation(BaseModel):
    """Schema for document citation."""

    document_id: int | UUID | str
    document_title: str
    similarity_score: float


class ChatResponse(BaseModel):
    """Response schema for chat endpoint."""

    response: str
    conversation_id: UUID | None = None
    citations: list[Citation] = []  # Citations from RAG documents
    context_source: str | None = None  # Source of context used (e.g., "PDF page 5", "Video 02:15-03:45")


class CitationRequest(BaseModel):
    """Request schema for citation finding endpoint."""

    book_id: UUID
    response_text: str
    similarity_threshold: float = 0.75


class BatchCitationRequest(BaseModel):
    """Request schema for batch citation finding."""

    book_id: UUID
    response_texts: list[str]
    similarity_threshold: float = 0.75


class CitationMatch(BaseModel):
    """Schema for a single citation match with position data."""

    text: str
    page: int
    coordinates: list[dict]  # List of bounding boxes with format [{"bbox": [x0, y0, x1, y1], "text": "..."}]
    similarity: float


class CitationResponse(BaseModel):
    """Response schema for citation endpoint."""

    citations: list[CitationMatch]


class BatchCitationResponse(BaseModel):
    """Response schema for batch citation endpoint."""

    citations: list[list[CitationMatch]]  # List of citation lists, one per response text
