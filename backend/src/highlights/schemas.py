
"""Pydantic schemas for highlights feature."""

import uuid
from datetime import datetime

from pydantic import ConfigDict, Field

from src.config.schema_casing import CamelModel


class HighlightCreate(CamelModel):
    """Schema for creating a new highlight."""

    source_data: dict[str, object] = Field(
        description="Web-highlighter source data containing startMeta, endMeta, text, etc."
    )


class HighlightResponse(CamelModel):
    """Schema for highlight response."""

    id: uuid.UUID
    user_id: uuid.UUID
    content_type: str
    content_id: uuid.UUID
    highlight_data: dict[str, object]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
