
"""Pydantic schemas for highlights feature."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HighlightCreate(BaseModel):
    """Schema for creating a new highlight."""

    source_data: dict[str, Any] = Field(
        ..., description="Web-highlighter source data containing startMeta, endMeta, text, etc."
    )


class HighlightResponse(BaseModel):
    """Schema for highlight response."""

    id: uuid.UUID
    user_id: uuid.UUID
    content_type: str
    content_id: uuid.UUID
    highlight_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
