"""User-related schemas for API endpoints."""

from pydantic import BaseModel


class UserSettingsResponse(BaseModel):
    """Response schema for user settings."""

    custom_instructions: str
    memory_count: int = 0


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
