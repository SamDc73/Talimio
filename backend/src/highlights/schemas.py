"""Pydantic schemas for the highlights feature."""

import uuid
from datetime import datetime

from pydantic import ConfigDict, Field

from src.config.schema_casing import CamelModel


class HighlightCreate(CamelModel):
    """Request body for creating or updating a highlight."""

    highlight_data: dict[str, object] = Field(
        description="Selected-text payload: text plus type-specific fields (page/position, cfi, or start/end time)."
    )


class HighlightResponse(CamelModel):
    """A stored highlight."""

    id: uuid.UUID
    user_id: uuid.UUID
    content_type: str
    content_id: uuid.UUID
    highlight_data: dict[str, object]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
