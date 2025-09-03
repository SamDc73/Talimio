"""Current user API endpoints for settings and memory management.

This router handles endpoints that operate on the currently authenticated user,
eliminating the need to pass user_id in the URL.
"""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import UserId
from src.database.session import get_db_session
from src.middleware.security import api_rate_limit
from src.user.schemas import (
    ClearMemoryResponse,
    CustomInstructionsRequest,
    CustomInstructionsResponse,
    PreferencesUpdateRequest,
    PreferencesUpdateResponse,
    UserPreferences,
    UserSettingsResponse,
)
from src.user.service import (
    _load_user_preferences,
    clear_user_memory,
    delete_user_memory,
    get_user_memories,
    get_user_settings,
    update_custom_instructions,
    update_user_preferences,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/user", tags=["current-user"])


@router.get("/settings")
async def get_current_user_settings(
    user_id: UserId, db: Annotated[AsyncSession, Depends(get_db_session)]
) -> UserSettingsResponse:
    """
    Get current user settings including custom instructions and memory count.

    Returns
    -------
        UserSettingsResponse: User's personalization settings
    """
    try:
        return await get_user_settings(user_id, db)
    except Exception as e:
        logger.exception(f"Error in get_current_user_settings for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get user settings: {e}"
        ) from e


@router.put("/settings/instructions")
async def update_current_user_instructions(
    user_id: UserId, request: CustomInstructionsRequest, db: Annotated[AsyncSession, Depends(get_db_session)]
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
        return await update_custom_instructions(user_id, request.instructions, db)
    except Exception as e:
        logger.exception(f"Error in update_current_user_instructions for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update instructions: {e}"
        ) from e


@router.delete("/memory")
async def clear_current_user_memory(user_id: UserId) -> ClearMemoryResponse:
    """
    Clear all stored memories for the current user.

    Returns
    -------
        ClearMemoryResponse: Success status and message
    """
    try:
        return await clear_user_memory(user_id)
    except Exception as e:
        logger.exception(f"Error in clear_current_user_memory for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to clear memory: {e}"
        ) from e


@router.get("/memories")
async def get_current_user_memories(user_id: UserId) -> dict[str, Any]:
    """
    Get all memories for the current user.

    Returns
    -------
        Dict with memories list and total count
    """
    try:
        memories = await get_user_memories(user_id)
        return {"memories": memories, "total": len(memories)}
    except Exception as e:
        logger.exception(f"Error in get_current_user_memories for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get memories: {e}"
        ) from e


@router.delete("/memories/{memory_id}")
async def delete_current_user_memory(user_id: UserId, memory_id: str) -> dict[str, str]:
    """
    Delete a specific memory for the current user.

    Args:
        memory_id: The ID of the memory to delete

    Returns
    -------
        Dict with deletion confirmation
    """
    try:
        result = await delete_user_memory(user_id, memory_id)
        if result:
            return {"status": "success", "message": "Memory deleted successfully"}
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found or deletion failed")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in delete_current_user_memory for user {user_id}, memory {memory_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete memory: {e}"
        ) from e


@router.put("/preferences")
@api_rate_limit
async def update_current_user_preferences(
    request: Request,  # Required for rate limiting decorator
    user_id: UserId,
    preferences_request: PreferencesUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
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
        return await update_user_preferences(user_id, preferences_request.preferences, db)
    except Exception as e:
        logger.exception(f"Error in update_current_user_preferences for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update preferences: {e}"
        ) from e


@router.get("/preferences")
@api_rate_limit
async def get_current_user_preferences(
    request: Request,  # Required for rate limiting decorator
    user_id: UserId,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserPreferences:
    """
    Get current user preferences.

    Returns
    -------
        UserPreferences: Current user preferences
    """
    try:
        return await _load_user_preferences(user_id, db)
    except Exception as e:
        logger.exception(f"Error in get_current_user_preferences for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get preferences: {e}"
        ) from e
