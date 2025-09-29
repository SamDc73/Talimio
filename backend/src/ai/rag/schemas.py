"""RAG system Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DocumentUpload(BaseModel):
    """Schema for document upload request."""

    document_type: str = Field(..., description="Type of document: 'pdf' or 'url'")
    title: str = Field(..., description="Title for the document")
    url: str | None = Field(None, description="URL for URL-type documents")


class DocumentResponse(BaseModel):
    """Schema for document response."""

    id: int
    course_id: uuid.UUID = Field(..., alias="roadmap_id")  # Maps to roadmap_id in DB
    document_type: str
    title: str
    file_path: str | None = None
    url: str | None = None
    source_url: str | None = None
    crawl_date: datetime | None = None
    content_hash: str | None = None
    # Removed doc_metadata - not used for course documents, only for books
    created_at: datetime
    processed_at: datetime | None = None
    embedded_at: datetime | None = None
    status: str


class DocumentList(BaseModel):
    """Schema for paginated document list response."""

    documents: list[DocumentResponse]
    total: int
    page: int
    size: int


# Removed unused DocumentChunkResponse class


class SearchRequest(BaseModel):
    """Schema for RAG search request."""

    query: str = Field(..., description="Search query")
    top_k: int = Field(default=5, description="Number of results to return")


class SearchResult(BaseModel):
    """Schema for RAG search result."""

    chunk_id: str = Field(..., description="Unique chunk identifier")
    content: str = Field(..., description="Chunk text content")
    similarity_score: float = Field(..., description="Similarity score (0-1)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")


class SearchResponse(BaseModel):
    """Schema for RAG search response."""

    results: list[SearchResult]
    total: int


class DefaultResponse(BaseModel):
    """Standard response following best practices."""

    status: bool
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
