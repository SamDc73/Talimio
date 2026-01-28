"""Pydantic schemas for tagging API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TagBase(BaseModel):
    """Base schema for tags."""

    name: str = Field(..., min_length=1, max_length=100)
    category: str | None = Field(None, max_length=50)
    color: str | None = Field(None, pattern="^#[0-9A-Fa-f]{6}$")  # Hex color validation


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


class ContentTagsUpdate(BaseModel):
    """Schema for updating content tags."""

    tags: list[str] = Field(..., max_length=20)


class TaggingResponse(BaseModel):
    """Response schema for tagging operations."""

    content_id: UUID
    content_type: str
    tags: list[str]
    auto_generated: bool = True
    success: bool = True
    error: str | None = None

