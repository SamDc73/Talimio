"""User-related schemas for API endpoints."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field, JsonValue

from src.config.schema_casing import CamelModel


class UserPreferences(CamelModel):
    """User preferences model."""

    theme: str = "system"
    user_preferences: dict[str, JsonValue] | None = None


class UserSettingsResponse(CamelModel):
    """Response schema for user settings."""

    custom_instructions: str
    memory_count: int = 0
    preferences: UserPreferences = Field(default_factory=UserPreferences)


class CustomInstructionsRequest(CamelModel):
    """Request schema for updating custom instructions."""

    instructions: str


class CustomInstructionsResponse(CamelModel):
    """Response schema for custom instructions."""

    instructions: str
    updated: bool = True


class ClearMemoryResponse(CamelModel):
    """Response schema for clearing user memory."""

    cleared: bool = True
    message: str = "All memories cleared successfully"


class DeleteMemoryResponse(CamelModel):
    """Response schema for deleting one user memory."""

    deleted: bool = True
    message: str = "Memory deleted successfully"


class ProfileSlotItem(CamelModel):
    """One active profile slot with provenance — what the product remembers."""

    id: uuid.UUID
    slot: str
    value: str
    source: Literal["manual", "inferred"]
    updated_at: datetime
    last_evidence_at: datetime | None = None
    evidence_text: str | None = None
    source_message_id: str | None = None


class UserMemoriesResponse(CamelModel):
    """Current user's profile-slot memories."""

    memories: list[ProfileSlotItem]
    total: int


class ProfileSlotUpdateRequest(CamelModel):
    """Manual value for one profile slot."""

    value: str


class ProfileSlotResponse(CamelModel):
    """Outcome of a manual slot operation."""

    slot: str
    # Mirrors memory's CommitStatus literals (set_profile_slot) plus "cleared"
    # (clear endpoint) so both endpoints emit values from one aligned set.
    status: Literal["applied", "noop", "rejected_stale", "rejected_manual", "cleared"]
