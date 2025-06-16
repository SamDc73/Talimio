"""Pydantic schemas for tagging API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TagBase(BaseModel):
    """Base schema for tags."""

    name: str = Field(..., min_length=1, max_length=100)
    category: str | None = Field(None, max_length=50)
    color: str | None = Field(None, pattern="^#[0-9A-Fa-f]{6}$")  # Hex color validation


class TagCreate(TagBase):
    """Schema for creating a tag."""


class TagUpdate(BaseModel):
    """Schema for updating a tag."""

    category: str | None = Field(None, max_length=50)
    color: str | None = Field(None, pattern="^#[0-9A-Fa-f]{6}$")


class TagSchema(TagBase):
    """Schema for tag responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    usage_count: int
    created_at: datetime
    updated_at: datetime


class TagWithConfidence(BaseModel):
    """Tag with confidence score."""

    tag: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class TagAssociationBase(BaseModel):
    """Base schema for tag associations."""

    tag_id: UUID
    content_id: UUID
    content_type: str = Field(..., pattern="^(book|video|roadmap)$")
    confidence_score: float = Field(1.0, ge=0.0, le=1.0)
    auto_generated: bool = True


class TagAssociationCreate(TagAssociationBase):
    """Schema for creating a tag association."""


class TagAssociationSchema(TagAssociationBase):
    """Schema for tag association responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    tag: TagSchema | None = None


class ContentTagsUpdate(BaseModel):
    """Schema for updating content tags."""

    tags: list[str] = Field(..., max_length=20)


class TagSuggestionRequest(BaseModel):
    """Request schema for tag suggestions."""

    content_type: str = Field(..., pattern="^(book|video|roadmap)$")
    title: str = Field(..., min_length=1)
    content_preview: str = Field(..., min_length=1, max_length=5000)


class BatchTaggingRequest(BaseModel):
    """Request schema for batch tagging."""

    items: list[dict[str, str]] = Field(
        ...,
        description="List of items with content_id, content_type, and optional title",
    )


class TaggingResponse(BaseModel):
    """Response schema for tagging operations."""

    content_id: UUID
    content_type: str
    tags: list[str]
    auto_generated: bool = True
    success: bool = True
    error: str | None = None


class BatchTaggingResponse(BaseModel):
    """Response schema for batch tagging operations."""

    results: list[TaggingResponse]
    total: int
    successful: int
    failed: int
