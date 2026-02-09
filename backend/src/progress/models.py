"""Pydantic models for progress tracking."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    completed_lessons: list[str] | None = []

    # Generic
    last_accessed: datetime | None = None
    notes: str | None = None


class ProgressUpdate(BaseModel):
    """Request model for updating progress."""

    progress_percentage: float = Field(..., ge=0, le=100)
    metadata: dict[str, Any] | None = Field(default_factory=dict)

    @field_validator("progress_percentage")
    @classmethod
    def round_percentage(cls, v: float) -> float:
        """Round percentage to 2 decimal places."""
        return round(v, 2)


class ProgressResponse(BaseModel):
    """Response model for progress data."""

    id: UUID | None
    content_id: UUID
    content_type: ContentType
    progress_percentage: float
    metadata: dict[str, Any]
    updated_at: datetime | None = None
    created_at: datetime | None = None


class BatchProgressRequest(BaseModel):
    """Request model for batch progress fetching."""

    content_ids: list[UUID] = Field(..., max_length=100, alias="contentIds")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("content_ids")
    @classmethod
    def validate_content_ids(cls, v: list[UUID]) -> list[UUID]:
        """Ensure unique content IDs."""
        return list(set(v))


class ProgressData(BaseModel):
    """Progress data with metadata."""

    progress_percentage: float = Field(alias="progressPercentage")
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class BatchProgressResponse(BaseModel):
    """Response model for batch progress data."""

    progress: dict[str, ProgressData]  # content_id -> ProgressData
