from datetime import datetime
from uuid import UUID

from pydantic import BaseModel as PydanticBaseModel


class UserBase(PydanticBaseModel):  # type: ignore[misc]
    """Base schema for user data."""

    email: str
    name: str


class UserCreate(UserBase):
    """Schema for creating a user."""


class UserUpdate(PydanticBaseModel):  # type: ignore[misc]
    """Schema for updating a user."""

    email: str | None = None
    name: str | None = None


class UserResponse(UserBase):
    """Schema for user response."""

    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        """Configuration for Pydantic model to support ORM model conversion."""

        from_attributes = True
