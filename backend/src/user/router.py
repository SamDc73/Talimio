"""Current user API endpoints for settings and memory management.

This router handles endpoints that operate on the currently authenticated user,
eliminating the need to pass user_id in the URL.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from src.auth import CurrentAuth
from src.middleware.security import api_rate_limit, create_rate_limit_dependency
from src.user.schemas import (
    CustomInstructionsRequest,
    CustomInstructionsResponse,
    PreferencesUpdateRequest,
    PreferencesUpdateResponse,
    UserPreferences,
    UserSettingsResponse,
)
from src.user.service import (
    _load_user_preferences,
    delete_user_memory,
    get_user_memories,
    get_user_settings,
    update_custom_instructions,
    update_user_preferences,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/user",
    tags=["current-user"],
    dependencies=[Depends(create_rate_limit_dependency(api_rate_limit))]
)


@router.get("/settings")
async def get_current_user_settings(
    auth: CurrentAuth
) -> UserSettingsResponse:
    """
    Get current user settings including custom instructions and memory count.

    Returns
    -------
        UserSettingsResponse: User's personalization settings
    """
    try:
        return await get_user_settings(auth.user_id, auth.session)
    except Exception as e:
        logger.exception(f"Error in get_current_user_settings for user {auth.user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get user settings: {e}"
        ) from e


@router.put("/settings/instructions")
async def update_current_user_instructions(
    auth: CurrentAuth, request: CustomInstructionsRequest
) -> CustomInstructionsResponse:
    """
    Update custom instructions for AI personalization for current user.

    Args:
        request: Custom instructions to set

    Returns
    -------
        CustomInstructionsResponse: Updated instructions and success status
    """
    try:
        return await update_custom_instructions(auth.user_id, request.instructions, auth.session)
    except Exception as e:
        logger.exception(f"Error in update_current_user_instructions for user {auth.user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update instructions: {e}"
        ) from e


@router.get("/memories")
async def get_current_user_memories(auth: CurrentAuth) -> dict[str, Any]:
    """
    Get all memories for the current user.

    Returns
    -------
        Dict with memories list and total count
    """
    try:
        memories = await get_user_memories(auth.user_id)
        return {"memories": memories, "total": len(memories)}
    except Exception as e:
        logger.exception(f"Error in get_current_user_memories for user {auth.user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get memories: {e}"
        ) from e


@router.delete("/memories/{memory_id}")
async def delete_current_user_memory(auth: CurrentAuth, memory_id: str) -> dict[str, str]:
    """
    Delete a specific memory for the current user.

    Args:
        memory_id: The ID of the memory to delete

    Returns
    -------
        Dict with deletion confirmation
    """
    try:
        result = await delete_user_memory(auth.user_id, memory_id)
        if result:
            return {"status": "success", "message": "Memory deleted successfully"}
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found or deletion failed")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in delete_current_user_memory for user {auth.user_id}, memory {memory_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete memory: {e}"
        ) from e


@router.put("/preferences")
async def update_current_user_preferences(
    auth: CurrentAuth,
    preferences_request: PreferencesUpdateRequest,
) -> PreferencesUpdateResponse:
    """
    Update preferences for the current user with partial updates.

    Accepts partial preference updates - only specified fields will be changed.
    Unspecified fields will retain their current values.

    Args:
        preferences_request: Partial preferences to update

    Returns
    -------
        PreferencesUpdateResponse: Updated complete preferences and success status
    """
    try:
        return await update_user_preferences(auth.user_id, preferences_request.preferences, auth.session)
    except Exception as e:
        logger.exception(f"Error in update_current_user_preferences for user {auth.user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update preferences: {e}"
        ) from e


@router.get("/preferences")
async def get_current_user_preferences(
    auth: CurrentAuth,
) -> UserPreferences:
    """
    Get current user preferences.

    Returns
    -------
        UserPreferences: Current user preferences
    """
    try:
        return await _load_user_preferences(auth.user_id, auth.session)
    except Exception as e:
        logger.exception(f"Error in get_current_user_preferences for user {auth.user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get preferences: {e}"
        ) from e
