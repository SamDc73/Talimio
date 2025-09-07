"""RAG system Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Any

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field


class CustomBaseModel(BaseModel):
    """Custom base model following best practices."""

    model_config = ConfigDict(
        from_attributes=True,  # Support ORM models
        use_enum_values=True,
        validate_assignment=True,
        populate_by_name=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
            uuid.UUID: lambda v: str(v),
        },
    )

    def serializable_dict(self, **kwargs: Any) -> dict[str, Any]:
        """Return dict with only serializable fields."""
        return jsonable_encoder(self.model_dump(**kwargs))


class DocumentUpload(CustomBaseModel):
    """Schema for document upload request."""

    document_type: str = Field(..., description="Type of document: 'pdf' or 'url'")
    title: str = Field(..., description="Title for the document")
    url: str | None = Field(None, description="URL for URL-type documents")


class DocumentResponse(CustomBaseModel):
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
    doc_metadata: dict | None = Field(alias="metadata", default=None)
    created_at: datetime
    processed_at: datetime | None = None
    embedded_at: datetime | None = None
    status: str


class DocumentList(CustomBaseModel):
    """Schema for paginated document list response."""

    documents: list[DocumentResponse]
    total: int
    page: int
    size: int


# Removed unused DocumentChunkResponse class


class SearchRequest(CustomBaseModel):
    """Schema for RAG search request."""

    query: str = Field(..., description="Search query")
    top_k: int = Field(default=5, description="Number of results to return")


class SearchResult(CustomBaseModel):
    """Schema for RAG search result."""

    chunk_id: str = Field(..., description="Unique chunk identifier")
    content: str = Field(..., description="Chunk text content")
    similarity_score: float = Field(..., description="Similarity score (0-1)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")


class SearchResponse(CustomBaseModel):
    """Schema for RAG search response."""

    results: list[SearchResult]
    total: int


class DefaultResponse(CustomBaseModel):
    """Standard response following best practices."""

    status: bool
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
