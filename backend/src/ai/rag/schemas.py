"""RAG system Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, JsonValue, field_validator

from src.config.schema_casing import build_camel_config


CourseDocumentStatus = Literal["pending", "processing", "embedded", "failed"]


class DocumentResponse(BaseModel):
    """Schema for document response."""

    id: int
    course_id: uuid.UUID
    document_type: str
    title: str
    file_path: str | None = None
    content_hash: str | None = None
    created_at: datetime
    processed_at: datetime | None = None
    embedded_at: datetime | None = None
    status: CourseDocumentStatus

    model_config = build_camel_config()


class DocumentList(BaseModel):
    """Schema for paginated document list response."""

    documents: list[DocumentResponse]
    total: int
    page: int
    size: int

    model_config = build_camel_config()


class SearchRequest(BaseModel):
    """Schema for RAG search request."""

    query: str = Field(min_length=1, description="Search query")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results to return")

    model_config = build_camel_config()

    @field_validator("query")
    @classmethod
    def _query_must_contain_text(cls, value: str) -> str:
        if value.strip():
            return value
        message = "Search query must not be empty"
        raise ValueError(message)


class SearchResult(BaseModel):
    """Schema for RAG search result."""

    chunk_id: str = Field(description="Unique chunk identifier")
    content: str = Field(description="Chunk text content")
    similarity_score: float = Field(description="Hybrid retrieval score used for result ordering")
    metadata: dict[str, JsonValue] = Field(default_factory=dict, description="Chunk metadata")

    model_config = build_camel_config()


class SearchResponse(BaseModel):
    """Schema for RAG search response."""

    results: list[SearchResult]
    total: int

    model_config = build_camel_config()


class DefaultResponse(BaseModel):
    """Standard response following best practices."""

    status: bool
    message: str
    details: dict[str, JsonValue] = Field(default_factory=dict)

    model_config = build_camel_config()
