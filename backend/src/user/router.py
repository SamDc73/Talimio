"""Current user API endpoints for settings and memory management.

This router handles endpoints that operate on the currently authenticated user,
eliminating the need to pass user_id in the URL.
"""

from typing import Annotated

from fastapi import APIRouter, Query

from src.auth import CurrentAuth
from src.user.schemas import (
    ClearMemoryResponse,
    CustomInstructionsRequest,
    CustomInstructionsResponse,
    DeleteMemoryResponse,
    ProfileSlotResponse,
    ProfileSlotUpdateRequest,
    UserMemoriesResponse,
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


@router.get("/settings")
async def get_current_user_settings(auth: CurrentAuth) -> UserSettingsResponse:
    """Get current user settings including custom instructions and memory count."""
    return await get_user_settings(auth.user_id, auth.session)


@router.put("/settings/instructions")
async def update_current_user_instructions(
    auth: CurrentAuth,
    request: CustomInstructionsRequest,
) -> CustomInstructionsResponse:
    """Update custom instructions for AI personalization for current user."""
    return await update_custom_instructions(auth.user_id, request.instructions, auth.session)


@router.get("/memories")
async def get_current_user_memories(
    auth: CurrentAuth,
    limit: Annotated[int, Query(ge=1, le=100, description="Max memories to return")] = 100,
) -> UserMemoriesResponse:
    """List the current user's active profile slots with provenance."""
    memories = await get_user_memories(auth.user_id, auth.session, limit=limit)
    return UserMemoriesResponse(memories=memories, total=len(memories))


@router.delete("/memories")
async def clear_current_user_memories(auth: CurrentAuth) -> ClearMemoryResponse:
    """Delete all memories for the current user."""
    await clear_user_memories(auth.user_id, auth.session)
    return ClearMemoryResponse(cleared=True, message="All memories cleared successfully")


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
async def delete_current_user_memory(auth: CurrentAuth, memory_id: str) -> DeleteMemoryResponse:
    """Forget one profile-slot memory: deactivate it and tombstone its evidence."""
    await delete_user_memory(auth.user_id, memory_id, auth.session)
    return DeleteMemoryResponse(deleted=True, message="Memory deleted successfully")
