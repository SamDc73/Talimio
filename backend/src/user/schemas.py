"""User-related schemas for API endpoints."""

from typing import Any

from pydantic import BaseModel, Field

from src.config.schema_casing import build_camel_config


class UserPreferences(BaseModel):
    """User preferences model."""

    theme: str = "system"
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
