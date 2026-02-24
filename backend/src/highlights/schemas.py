
"""Pydantic schemas for highlights feature."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from src.config.schema_casing import build_camel_config


class HighlightCreate(BaseModel):
    """Schema for creating a new highlight."""

    source_data: dict[str, Any] = Field(
        ..., description="Web-highlighter source data containing startMeta, endMeta, text, etc."
    )

    model_config = build_camel_config()


class HighlightResponse(BaseModel):
    """Schema for highlight response."""

    id: uuid.UUID
    user_id: uuid.UUID
    content_type: str
    content_id: uuid.UUID
    highlight_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = build_camel_config(from_attributes=True)
