"""User API endpoints for settings and memory management."""

import logging
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status

from src.user.schemas import (
    ClearMemoryResponse,
    CustomInstructionsRequest,
    CustomInstructionsResponse,
    UserSettingsResponse,
)
from src.user.service import clear_user_memory, get_user_settings, update_custom_instructions


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/user", tags=["user"])


def get_user_id_from_header(x_user_id: str | None = Header(None)) -> str:
    """Extract user_id from header, with fallback to default."""
    if not x_user_id:
        # For development/demo purposes, use a default user ID
        # In production, this should be extracted from JWT token or session
        return "demo_user"
    return x_user_id


@router.get("/settings")
async def get_settings(
    user_id: Annotated[str, Header(alias="x-user-id")] = "demo_user"
) -> UserSettingsResponse:
    """
    Get user settings including custom instructions and memory count.

    Headers:
        x-user-id: User identifier (optional, defaults to demo_user)

    Returns
    -------
        UserSettingsResponse: User's personalization settings
    """
    try:
        return await get_user_settings(user_id)
    except Exception as e:
        logger.exception(f"Error in get_settings for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user settings: {e}"
        ) from e


@router.put("/settings/instructions")
async def update_instructions(
    request: CustomInstructionsRequest,
    user_id: Annotated[str, Header(alias="x-user-id")] = "demo_user"
) -> CustomInstructionsResponse:
    """
    Update custom instructions for AI personalization.

    Headers:
        x-user-id: User identifier (optional, defaults to demo_user)

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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update instructions: {e}"
        ) from e


@router.delete("/memory")
async def clear_memory(
    user_id: Annotated[str, Header(alias="x-user-id")] = "demo_user"
) -> ClearMemoryResponse:
    """
    Clear all stored memories for the user.

    Headers:
        x-user-id: User identifier (optional, defaults to demo_user)

    Returns
    -------
        ClearMemoryResponse: Success status and message
    """
    try:
        return await clear_user_memory(user_id)
    except Exception as e:
        logger.exception(f"Error in clear_memory for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear memory: {e}"
        ) from e


@router.get("/settings/instructions")
async def get_instructions(
    user_id: Annotated[str, Header(alias="x-user-id")] = "demo_user"
) -> dict[str, str]:
    """
    Get custom instructions for the user.

    Headers:
        x-user-id: User identifier (optional, defaults to demo_user)

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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get instructions: {e}"
        ) from e
