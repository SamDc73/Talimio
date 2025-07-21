"""Pydantic models for authentication."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """Base user model."""

    email: EmailStr
    username: str | None = None


class UserCreate(UserBase):
    """User creation model."""

    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    """User update model."""

    email: EmailStr | None = None
    username: str | None = None
    password: str | None = Field(None, min_length=8)


class UserInDB(UserBase):
    """User model as stored in database."""

    id: UUID
    created_at: datetime
    updated_at: datetime | None = None
    is_active: bool = True
    is_verified: bool = False
    metadata: dict[str, Any] | None = None


class UserResponse(UserBase):
    """User response model for API."""

    id: UUID
    created_at: datetime
    is_verified: bool = False


class TokenData(BaseModel):
    """Token payload data."""

    sub: str  # User ID
    email: str | None = None
    exp: int | None = None
    iat: int | None = None


class UserPreferences(BaseModel):
    """User preferences model."""

    theme: str = "light"
    language: str = "en"
    notifications_enabled: bool = True
    email_notifications: bool = True
    global_zoom: int = 100
