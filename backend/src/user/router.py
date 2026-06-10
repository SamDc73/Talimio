"""Current user API endpoints for settings and memory management.

This router handles endpoints that operate on the currently authenticated user,
eliminating the need to pass user_id in the URL.
"""

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.auth import CurrentAuth
from src.user.schemas import (
    ClearMemoryResponse,
    CustomInstructionsRequest,
    CustomInstructionsResponse,
    UserSettingsResponse,
)
from src.user.service import (
    clear_profile_slot,
    clear_user_memories,
    delete_user_memory,
    get_user_memories,
    get_user_settings,
    set_profile_slot,
    update_custom_instructions,
)


router = APIRouter(
    prefix="/api/v1/user",
    tags=["current-user"],
)


class UserMemoriesResponse(BaseModel):
    """Current user's memory list response."""

    memories: Sequence[object]
    total: int


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
) -> UserMemoriesResponse:
    """
    Get all memories for the current user.

    Returns
    -------
        Dict with memories list and total count
    """
    memories = await get_user_memories(auth.user_id, auth.session, limit=limit)
    return UserMemoriesResponse(memories=memories, total=len(memories))


@router.delete("/memories")
async def clear_current_user_memories(auth: CurrentAuth) -> ClearMemoryResponse:
    """Delete all memories for the current user."""
    await clear_user_memories(auth.user_id, auth.session)
    return ClearMemoryResponse(cleared=True, message="All memories cleared successfully")


class ProfileSlotUpdateRequest(BaseModel):
    """Manual value for one profile slot."""

    value: str


class ProfileSlotResponse(BaseModel):
    """Outcome of a manual slot operation."""

    slot: str
    status: str


@router.put("/memories/slots/{slot}")
async def set_current_user_profile_slot(
    auth: CurrentAuth,
    slot: str,
    request: ProfileSlotUpdateRequest,
) -> ProfileSlotResponse:
    """Manually set a profile slot; manual values win over inferred ones."""
    result = await set_profile_slot(auth.user_id, slot, request.value, auth.session)
    return ProfileSlotResponse(slot=result.slot, status=result.status)


@router.delete("/memories/slots/{slot}")
async def clear_current_user_profile_slot(
    auth: CurrentAuth,
    slot: str,
    forget: Annotated[bool, Query(description="Also tombstone the slot's raw evidence")] = False,
) -> ProfileSlotResponse:
    """Clear a profile slot; with forget=true the raw evidence is redacted too."""
    await clear_profile_slot(auth.user_id, slot, auth.session, forget=forget)
    return ProfileSlotResponse(slot=slot, status="cleared")


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
    await delete_user_memory(auth.user_id, memory_id, auth.session)
    return {"status": "success", "message": "Memory deleted successfully"}
