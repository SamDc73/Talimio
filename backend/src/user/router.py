"""User API endpoints for settings and memory management."""

import logging
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status

from src.user.schemas import (
    ClearMemoryResponse,
    CustomInstructionsRequest,
    CustomInstructionsResponse,
    PreferencesUpdateRequest,
    PreferencesUpdateResponse,
    UserSettingsResponse,
)
from src.user.service import (
    clear_user_memory,
    get_user_memories,
    get_user_settings,
    update_custom_instructions,
    update_user_preferences,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/user", tags=["user"])


def get_user_id_from_header(x_user_id: str | None = Header(None)) -> str:
    """Extract user_id from header, with fallback to default."""
    if not x_user_id:
        # For development/demo purposes, use a default user ID that has existing memories
        # In production, this should be extracted from JWT token or session
        return "demo_user_123"
    return x_user_id


@router.get("/settings")
async def get_settings(user_id: Annotated[str, Header(alias="x-user-id")] = "demo_user_123") -> UserSettingsResponse:
    """
    Get user settings including custom instructions and memory count.

    Headers:
        x-user-id: User identifier (optional, defaults to demo_user_123)

    Returns
    -------
        UserSettingsResponse: User's personalization settings
    """
    try:
        return await get_user_settings(user_id)
    except Exception as e:
        logger.exception(f"Error in get_settings for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get user settings: {e}"
        ) from e


@router.put("/settings/instructions")
async def update_instructions(
    request: CustomInstructionsRequest, user_id: Annotated[str, Header(alias="x-user-id")] = "demo_user_123"
) -> CustomInstructionsResponse:
    """
    Update custom instructions for AI personalization.

    Headers:
        x-user-id: User identifier (optional, defaults to demo_user_123)

    Args:
        request: Custom instructions to set

    Returns
    -------
        CustomInstructionsResponse: Updated instructions and success status
    """
    try:
        return await update_custom_instructions(user_id, request.instructions)
    except Exception as e:
        logger.exception(f"Error in update_instructions for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update instructions: {e}"
        ) from e


@router.delete("/memory")
async def clear_memory(user_id: Annotated[str, Header(alias="x-user-id")] = "demo_user_123") -> ClearMemoryResponse:
    """
    Clear all stored memories for the user.

    Headers:
        x-user-id: User identifier (optional, defaults to demo_user_123)

    Returns
    -------
        ClearMemoryResponse: Success status and message
    """
    try:
        return await clear_user_memory(user_id)
    except Exception as e:
        logger.exception(f"Error in clear_memory for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to clear memory: {e}"
        ) from e


@router.get("/settings/instructions")
async def get_instructions(user_id: Annotated[str, Header(alias="x-user-id")] = "demo_user_123") -> dict[str, str]:
    """
    Get custom instructions for the user.

    Headers:
        x-user-id: User identifier (optional, defaults to demo_user_123)

    Returns
    -------
        Dict containing the user's custom instructions
    """
    try:
        settings = await get_user_settings(user_id)
        return {"instructions": settings.custom_instructions}
    except Exception as e:
        logger.exception(f"Error in get_instructions for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get instructions: {e}"
        ) from e


@router.get("/memories")
async def get_memories(user_id: Annotated[str, Header(alias="x-user-id")] = "demo_user_123") -> list[dict]:
    """
    Get all memories for the user.

    Headers:
        x-user-id: User identifier (optional, defaults to demo_user_123)

    Returns
    -------
        List of user memories with content and metadata
    """
    try:
        return await get_user_memories(user_id)
    except Exception as e:
        logger.exception(f"Error in get_memories for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get memories: {e}"
        ) from e


@router.put("/preferences")
async def update_preferences(
    request: PreferencesUpdateRequest, user_id: Annotated[str, Header(alias="x-user-id")] = "demo_user_123"
) -> PreferencesUpdateResponse:
    """
    Update user preferences.

    Headers:
        x-user-id: User identifier (optional, defaults to demo_user_123)

    Args:
        request: User preferences to update

    Returns
    -------
        PreferencesUpdateResponse: Updated preferences and success status
    """
    try:
        return await update_user_preferences(user_id, request.preferences)
    except Exception as e:
        logger.exception(f"Error in update_preferences for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update preferences: {e}"
        ) from e
