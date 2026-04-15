"""Current user API endpoints for settings and memory management.

This router handles endpoints that operate on the currently authenticated user,
eliminating the need to pass user_id in the URL.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Query

from src.auth import CurrentAuth
from src.user.schemas import (
    ClearMemoryResponse,
    CustomInstructionsRequest,
    CustomInstructionsResponse,
    UserSettingsResponse,
)
from src.user.service import (
    clear_user_memories,
    delete_user_memory,
    get_user_memories,
    get_user_settings,
    update_custom_instructions,
)


router = APIRouter(
    prefix="/api/v1/user",
    tags=["current-user"],
)


@router.get("/settings")
async def get_current_user_settings(
    auth: CurrentAuth,
) -> UserSettingsResponse:
    """
    Get current user settings including custom instructions and memory count.

    Returns
    -------
        UserSettingsResponse: User's personalization settings
    """
    return await get_user_settings(auth.user_id, auth.session)


@router.put("/settings/instructions")
async def update_current_user_instructions(
    auth: CurrentAuth,
    request: CustomInstructionsRequest,
) -> CustomInstructionsResponse:
    """
    Update custom instructions for AI personalization for current user.

    Args:
        request: Custom instructions to set

    Returns
    -------
        CustomInstructionsResponse: Updated instructions and success status
    """
    return await update_custom_instructions(auth.user_id, request.instructions, auth.session)


@router.get("/memories")
async def get_current_user_memories(
    auth: CurrentAuth,
    limit: Annotated[int, Query(ge=1, le=100, description="Max memories to return")] = 100,
) -> dict[str, Any]:
    """
    Get all memories for the current user.

    Returns
    -------
        Dict with memories list and total count
    """
    memories = await get_user_memories(auth.user_id, limit=limit)
    return {"memories": memories, "total": len(memories)}


@router.delete("/memories")
async def clear_current_user_memories(auth: CurrentAuth) -> ClearMemoryResponse:
    """Delete all memories for the current user."""
    await clear_user_memories(auth.user_id)
    return ClearMemoryResponse(cleared=True, message="All memories cleared successfully")


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
    await delete_user_memory(auth.user_id, memory_id)
    return {"status": "success", "message": "Memory deleted successfully"}
