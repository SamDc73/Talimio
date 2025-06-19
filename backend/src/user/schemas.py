"""User-related schemas for API endpoints."""

from typing import Any

from pydantic import BaseModel


class UserPreferences(BaseModel):
    """User preferences model."""

    theme: str = "system"
    language: str = "en"
    auto_play_videos: bool = True
    default_zoom_level: float = 1.0
    sidebar_open: bool = True
    sidebar_collapsed: bool = False
    notifications_enabled: bool = True
    onboarding_completed: bool = False
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
