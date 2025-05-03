from datetime import datetime
from uuid import UUID

from pydantic import BaseModel as PydanticBaseModel, Field


class ProgressBase(PydanticBaseModel):  # type: ignore[misc]
    """Base schema for progress data."""

    status: str = Field(..., pattern="^(not_started|in_progress|completed)$")


class ProgressCreate(ProgressBase):
    """Schema for creating progress."""

    user_id: UUID | None = None
    node_id: UUID


class ProgressUpdate(ProgressBase):
    """Schema for updating progress."""


class ProgressResponse(ProgressBase):
    """Schema for progress response."""

    id: UUID
    user_id: UUID
    node_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        """Configuration for Pydantic model to support ORM model conversion."""

        from_attributes = True
