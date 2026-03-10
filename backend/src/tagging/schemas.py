
"""Pydantic schemas for tagging API."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from src.config.schema_casing import build_camel_config


class TagBase(BaseModel):
    """Base schema for tags."""

    name: str = Field(..., min_length=1, max_length=100)
    category: str | None = Field(None, max_length=50)
    color: str | None = Field(None, pattern="^#[0-9A-Fa-f]{6}$")  # Hex color validation

    model_config = build_camel_config()


class TagSchema(TagBase):
    """Schema for tag responses."""

    model_config = build_camel_config(from_attributes=True)

    id: uuid.UUID
    usage_count: int
    created_at: datetime
    updated_at: datetime


class TagWithConfidence(BaseModel):
    """Tag with confidence score."""

    model_config = build_camel_config(extra="forbid")

    tag: str = Field(..., min_length=1, max_length=100)
    confidence: float = Field(..., ge=0.0, le=1.0)


class ContentTagsUpdate(BaseModel):
    """Schema for updating content tags."""

    tags: list[str] = Field(..., max_length=20)

    model_config = build_camel_config()


class TaggingResponse(BaseModel):
    """Response schema for tagging operations."""

    content_id: uuid.UUID
    content_type: str
    tags: list[str]
    auto_generated: bool = True
    success: bool = True
    error: str | None = None

    model_config = build_camel_config()
