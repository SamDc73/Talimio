"""User-related schemas for API endpoints."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, JsonValue

from src.config.schema_casing import build_camel_config


class UserPreferences(BaseModel):
    """User preferences model."""

    theme: str = "system"
    user_preferences: dict[str, JsonValue] | None = None

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


class DeleteMemoryResponse(BaseModel):
    """Response schema for deleting one user memory."""

    deleted: bool = True
    message: str = "Memory deleted successfully"

    model_config = build_camel_config()


class ProfileSlotItem(BaseModel):
    """One active profile slot with provenance — what the product remembers."""

    id: uuid.UUID
    slot: str
    value: str
    source: Literal["manual", "inferred"]
    updated_at: datetime
    last_evidence_at: datetime | None = None
    evidence_text: str | None = None
    source_message_id: str | None = None

    model_config = build_camel_config()


class UserMemoriesResponse(BaseModel):
    """Current user's profile-slot memories."""

    memories: list[ProfileSlotItem]
    total: int

    model_config = build_camel_config()


class ProfileSlotUpdateRequest(BaseModel):
    """Manual value for one profile slot."""

    value: str

    model_config = build_camel_config()


class ProfileSlotResponse(BaseModel):
    """Outcome of a manual slot operation."""

    slot: str
    # Mirrors memory's CommitStatus literals (set_profile_slot) plus "cleared"
    # (clear endpoint) so both endpoints emit values from one aligned set.
    status: Literal["applied", "noop", "rejected_stale", "rejected_manual", "cleared"]

    model_config = build_camel_config()
