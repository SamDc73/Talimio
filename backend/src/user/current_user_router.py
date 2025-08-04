"""Current user API endpoints for settings and memory management.

This router handles endpoints that operate on the currently authenticated user,
eliminating the need to pass user_id in the URL.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import UserId
from src.database.session import get_db_session
from src.user.schemas import (
    ClearMemoryResponse,
    CustomInstructionsRequest,
    CustomInstructionsResponse,
    UserSettingsResponse,
)
from src.user.service import (
    clear_user_memory,
    get_user_memories,
    get_user_settings,
    update_custom_instructions,
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
    user_id: UserId, request: CustomInstructionsRequest
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
        return await update_custom_instructions(user_id, request.instructions)
    except Exception as e:
        logger.exception(f"Error in update_current_user_instructions for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update instructions: {e}"
        ) from e


@router.get("/settings/instructions")
async def get_current_user_instructions(
    user_id: UserId, db: Annotated[AsyncSession, Depends(get_db_session)]
) -> dict[str, str]:
    """
    Get custom instructions for the current user.

    Returns
    -------
        Dict containing the user's custom instructions
    """
    try:
        settings = await get_user_settings(user_id, db)
        return {"instructions": settings.custom_instructions}
    except Exception as e:
        logger.exception(f"Error in get_current_user_instructions for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get instructions: {e}"
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
async def get_current_user_memories(user_id: UserId) -> list[dict]:
    """
    Get all memories for the current user.

    Returns
    -------
        List of user memories with content and metadata
    """
    try:
        return await get_user_memories(user_id)
    except Exception as e:
        logger.exception(f"Error in get_current_user_memories for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to get memories: {e}"
        ) from e
