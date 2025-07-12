"""User API endpoints for settings and memory management."""

import logging

from fastapi import APIRouter, Header, HTTPException, status

from src.user.schemas import (
    ClearMemoryResponse,
    CustomInstructionsRequest,
    CustomInstructionsResponse,
    PreferencesUpdateRequest,
    PreferencesUpdateResponse,
    UserCreate,
    UserSettingsResponse,
    UserUpdate,
)
from src.user.service import (
    clear_user_memory,
    create_user,
    delete_user,
    get_user,
    get_user_memories,
    get_user_settings,
    update_custom_instructions,
    update_user,
    update_user_preferences,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/users", tags=["user"])


def get_user_id_from_header(x_user_id: str | None = Header(None)) -> str:
    """Extract user_id from header, with fallback to default."""
    if not x_user_id:
        # For development/demo purposes, use a default user ID that has existing memories
        # In production, this should be extracted from JWT token or session
        return "demo_user_123"
    return x_user_id


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user_endpoint(user: UserCreate):
    return await create_user(user)


@router.get("/{user_id}")
async def get_user_endpoint(user_id: str):
    return await get_user(user_id)


@router.put("/{user_id}")
async def update_user_endpoint(user_id: str, user: UserUpdate):
    return await update_user(user_id, user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_endpoint(user_id: str):
    await delete_user(user_id)
    return {"message": "User deleted successfully"}


@router.get("/{user_id}/settings")
async def get_settings(user_id: str) -> UserSettingsResponse:
    """
    Get user settings including custom instructions and memory count.

    Args:
        user_id: User identifier

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


@router.put("/{user_id}/settings/instructions")
async def update_instructions(
    user_id: str, request: CustomInstructionsRequest
) -> CustomInstructionsResponse:
    """
    Update custom instructions for AI personalization.

    Args:
        user_id: User identifier
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


@router.delete("/{user_id}/memory")
async def clear_memory(user_id: str) -> ClearMemoryResponse:
    """
    Clear all stored memories for the user.

    Args:
        user_id: User identifier

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


@router.get("/{user_id}/settings/instructions")
async def get_instructions(user_id: str) -> dict[str, str]:
    """
    Get custom instructions for the user.

    Args:
        user_id: User identifier

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


@router.get("/{user_id}/memories")
async def get_memories(user_id: str) -> list[dict]:
    """
    Get all memories for the user.

    Args:
        user_id: User identifier

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


@router.put("/{user_id}/preferences")
async def update_preferences(
    user_id: str, request: PreferencesUpdateRequest
) -> PreferencesUpdateResponse:
    """
    Update user preferences.

    Args:
        user_id: User identifier
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

