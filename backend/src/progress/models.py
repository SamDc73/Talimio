
"""Pydantic models for progress tracking."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, JsonValue, field_validator


ContentType = Literal["book", "video", "course"]


class ProgressMetadata(BaseModel):
    """Type-specific metadata for progress tracking."""

    # Book-specific
    current_page: int | None = None
    total_pages: int | None = None

    # Video-specific
    position: float | None = None  # Seconds
    duration: float | None = None  # Total duration in seconds

    # Course-specific
    completed_lessons: list[str] | None = Field(default_factory=list)

    # Generic
    last_accessed: datetime | None = None
    notes: str | None = None


class ProgressUpdate(BaseModel):
    """Request model for updating progress."""

    progress_percentage: float = Field(ge=0, le=100)
    metadata: dict[str, JsonValue] | None = Field(default_factory=dict)

    @field_validator("progress_percentage")
    @classmethod
    def round_percentage(cls, v: float) -> float:
        """Round percentage to 2 decimal places."""
        return round(v, 2)


class ProgressResponse(BaseModel):
    """Response model for progress data."""

    id: uuid.UUID | None
    content_id: uuid.UUID
    content_type: ContentType
    progress_percentage: float
    metadata: dict[str, JsonValue]
    updated_at: datetime | None = None
    created_at: datetime | None = None
