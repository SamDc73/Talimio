"""Pydantic schemas for authentication."""

from uuid import UUID

from pydantic import BaseModel, Field


class UserRegister(BaseModel):
    """Schema for user registration."""

    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    """Schema for user login."""

    username: str
    password: str


class UserResponse(BaseModel):
    """Schema for user response (no password)."""

    id: UUID
    username: str
    email: str | None = None
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


class Token(BaseModel):
    """Schema for JWT token response."""

    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Schema for token payload data."""

    user_id: str
    username: str | None = None


class PasswordChange(BaseModel):
    """Schema for password change request."""

    old_password: str
    new_password: str = Field(..., min_length=6)


class UserUpdate(BaseModel):
    """Schema for updating user info."""

    username: str | None = Field(None, min_length=3, max_length=100)
