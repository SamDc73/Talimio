from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class UserBase(BaseModel):
    """Base schema for user data."""

    # Change email to regular str
    email: str  # Changed from EmailStr
    name: str


class UserCreate(UserBase):
    """Schema for creating a user."""



class UserUpdate(BaseModel):
    """Schema for updating a user."""

    # Change email to regular str
    email: str | None = None  # Changed from EmailStr
    name: str | None = None


class UserResponse(UserBase):
    """Schema for user response."""

    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
