"""RAG system Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentUpload(BaseModel):
    """Schema for document upload request."""

    document_type: str = Field(..., description="Type of document: 'pdf' or 'url'")
    title: str = Field(..., description="Title for the document")
    url: str | None = Field(None, description="URL for URL-type documents")


class DocumentResponse(BaseModel):
    """Schema for document response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    roadmap_id: uuid.UUID
    document_type: str
    title: str
    file_path: str | None = None
    url: str | None = None
    source_url: str | None = None
    crawl_date: datetime | None = None
    content_hash: str | None = None
    metadata: dict | None = None
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


class DocumentChunkResponse(BaseModel):
    """Schema for document chunk response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    node_id: str
    chunk_index: int
    content: str
    token_count: int | None = None
    metadata: dict | None = None
    created_at: datetime


class SearchRequest(BaseModel):
    """Schema for RAG search request."""

    query: str = Field(..., description="Search query")
    top_k: int = Field(default=5, description="Number of results to return")


class SearchResult(BaseModel):
    """Schema for RAG search result."""

    document_id: int
    document_title: str
    chunk_content: str
    similarity_score: float
    metadata: dict | None = None


class SearchResponse(BaseModel):
    """Schema for RAG search response."""

    results: list[SearchResult]
    total: int
