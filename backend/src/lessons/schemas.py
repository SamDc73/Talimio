from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class LessonCreateRequest(BaseModel):
    """Request schema for creating a new lesson."""

    course_id: UUID
    slug: str
    node_meta: dict[str, Any]


class LessonUpdateRequest(BaseModel):
    """Request schema for updating a lesson."""

    slug: str | None = None
    md_source: str | None = None
    html_cache: str | None = None


class LessonCitation(BaseModel):
    """Schema for lesson document citation."""
    document_id: int
    document_title: str
    similarity_score: float

class LessonResponse(BaseModel):
    """Response schema representing a lesson, including metadata and content."""

    id: UUID
    course_id: UUID
    slug: str
    md_source: str
    html_cache: str | None = None
    created_at: datetime
    updated_at: datetime
    citations: list[LessonCitation] = []  # Citations from RAG documents
