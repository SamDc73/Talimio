
"""Pydantic models for progress tracking."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field, JsonValue, field_validator

from src.config.schema_casing import CamelModel


ContentType = Literal["book", "video", "course"]


class ProgressUpdate(CamelModel):
    """Request model for updating progress."""

    progress_percentage: float = Field(ge=0, le=100)
    metadata: dict[str, JsonValue] | None = Field(default_factory=dict)

    @field_validator("progress_percentage")
    @classmethod
    def round_percentage(cls, v: float) -> float:
        """Round percentage to 2 decimal places."""
        return round(v, 2)


class ProgressResponse(CamelModel):
    """Response model for progress data."""

    id: uuid.UUID | None
    content_id: uuid.UUID
    content_type: ContentType
    progress_percentage: float
    metadata: dict[str, JsonValue]
    updated_at: datetime | None = None
    created_at: datetime | None = None
