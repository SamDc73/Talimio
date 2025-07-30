"""User-related schemas for API endpoints."""

from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    """Base user model with common attributes."""

    email: EmailStr
    name: str | None = None


class UserCreate(UserBase):
    """Schema for creating a new user."""



class UserUpdate(UserBase):
    """Schema for updating user information."""



class User(UserBase):
    """Complete user model with ID."""

    id: str

    model_config = ConfigDict(from_attributes=True)


class UserPreferences(BaseModel):
    """User preferences model."""

    theme: str = "system"
    language: str = "en"
    auto_play_videos: bool = True
    default_zoom_level: float = 1.0
    sidebar_open: bool = True
    sidebar_collapsed: bool = False
    notifications_enabled: bool = True
    user_preferences: dict[str, Any] | None = None


class UserSettingsResponse(BaseModel):
    """Response schema for user settings."""

    custom_instructions: str
    memory_count: int = 0
    preferences: UserPreferences = UserPreferences()


class CustomInstructionsRequest(BaseModel):
    """Request schema for updating custom instructions."""

    instructions: str


class CustomInstructionsResponse(BaseModel):
    """Response schema for custom instructions."""

    instructions: str
    updated: bool = True


class ClearMemoryResponse(BaseModel):
    """Response schema for clearing user memory."""

    cleared: bool = True
    message: str = "All memories cleared successfully"


class PreferencesUpdateRequest(BaseModel):
    """Request schema for updating user preferences."""

    preferences: UserPreferences


class PreferencesUpdateResponse(BaseModel):
    """Response schema for preferences update."""

    preferences: UserPreferences
    updated: bool = True
