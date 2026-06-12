
"""Pydantic models for progress tracking."""

import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Literal

from pydantic import Field, JsonValue, field_serializer, field_validator
from pydantic.alias_generators import to_snake

from src.config.schema_casing import CamelModel, to_camel


ContentType = Literal["book", "video", "course"]


def _convert_top_level_keys(
    metadata: dict[str, JsonValue], *, convert_key: Callable[[str], str]
) -> dict[str, JsonValue]:
    """Convert top-level keys only; nested dicts are data-keyed maps (book TOC ids, lesson UUIDs) whose keys must round-trip verbatim."""
    return {convert_key(str(key)): item for key, item in metadata.items()}


class ProgressUpdate(CamelModel):
    """Request model for updating progress."""

    progress_percentage: float = Field(ge=0, le=100)
    metadata: dict[str, JsonValue] | None = Field(default_factory=dict)

    @field_validator("progress_percentage")
    @classmethod
    def round_percentage(cls, v: float) -> float:
        """Round percentage to 2 decimal places."""
        return round(v, 2)

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_metadata_keys(cls, value: JsonValue | None) -> JsonValue | None:
        """Store metadata with snake_case top-level keys while accepting camelCase payloads."""
        if not isinstance(value, dict):
            return value
        return _convert_top_level_keys(value, convert_key=to_snake)


class ProgressResponse(CamelModel):
    """Response model for progress data."""

    id: uuid.UUID | None
    content_id: uuid.UUID
    content_type: ContentType
    progress_percentage: float
    metadata: dict[str, JsonValue]
    updated_at: datetime | None = None
    created_at: datetime | None = None

    @field_serializer("metadata")
    def serialize_metadata(self, metadata: dict[str, JsonValue]) -> dict[str, JsonValue]:
        """Serialize metadata with the same camelCase API contract as top-level fields."""
        return _convert_top_level_keys(metadata, convert_key=to_camel)
