"""
Pydantic schemas for highlights feature.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class HighlightCreate(BaseModel):
    """Schema for creating a new highlight."""

    source_data: dict[str, Any] = Field(
        ..., description="Web-highlighter source data containing startMeta, endMeta, text, etc."
    )


class HighlightResponse(BaseModel):
    """Schema for highlight response."""

    id: UUID
    user_id: UUID
    content_type: str
    content_id: UUID
    highlight_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
