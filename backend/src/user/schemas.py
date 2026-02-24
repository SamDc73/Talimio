"""User-related schemas for API endpoints."""

from typing import Any

from pydantic import BaseModel, Field

from src.config.schema_casing import build_camel_config


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

    model_config = build_camel_config()


class PartialUserPreferences(BaseModel):
    """Partial user preferences model for safe partial updates."""

    theme: str | None = None
    language: str | None = None
    auto_play_videos: bool | None = None
    default_zoom_level: float | None = None
    sidebar_open: bool | None = None
    sidebar_collapsed: bool | None = None
    notifications_enabled: bool | None = None
    user_preferences: dict[str, Any] | None = None

    model_config = build_camel_config()


class UserSettingsResponse(BaseModel):
    """Response schema for user settings."""

    custom_instructions: str
    memory_count: int = 0
    preferences: UserPreferences = Field(default_factory=UserPreferences)

    model_config = build_camel_config()


class CustomInstructionsRequest(BaseModel):
    """Request schema for updating custom instructions."""

    instructions: str

    model_config = build_camel_config()


class CustomInstructionsResponse(BaseModel):
    """Response schema for custom instructions."""

    instructions: str
    updated: bool = True

    model_config = build_camel_config()


class ClearMemoryResponse(BaseModel):
    """Response schema for clearing user memory."""

    cleared: bool = True
    message: str = "All memories cleared successfully"

    model_config = build_camel_config()


class PreferencesUpdateRequest(BaseModel):
    """Request schema for updating user preferences."""

    preferences: PartialUserPreferences

    model_config = build_camel_config()


class PreferencesUpdateResponse(BaseModel):
    """Response schema for preferences update."""

    preferences: UserPreferences
    updated: bool = True

    model_config = build_camel_config()
