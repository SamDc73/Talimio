"""User service for handling user settings and memory management."""

import logging

from src.ai.memory import get_memory_wrapper
from src.user.schemas import (
    ClearMemoryResponse,
    CustomInstructionsResponse,
    UserSettingsResponse,
)


logger = logging.getLogger(__name__)


async def get_user_settings(user_id: str) -> UserSettingsResponse:
    """
    Get user settings including custom instructions and memory count.

    Args:
        user_id: Unique identifier for the user

    Returns
    -------
        UserSettingsResponse: User's settings and memory information
    """
    try:
        memory_wrapper = get_memory_wrapper()

        # Get custom instructions
        custom_instructions = await memory_wrapper.get_custom_instructions(user_id)

        # Get memory count (try to search for all memories to count them)
        try:
            memories = await memory_wrapper.search_memories(
                user_id=user_id,
                query="",  # Empty query to get all memories
                limit=1000,  # High limit to count all
                relevance_threshold=0.0  # Include all memories
            )
            memory_count = len(memories)
        except Exception as e:
            logger.warning(f"Failed to count memories for user {user_id}: {e}")
            memory_count = 0

        return UserSettingsResponse(
            custom_instructions=custom_instructions,
            memory_count=memory_count
        )

    except Exception as e:
        logger.exception(f"Error getting user settings for {user_id}: {e}")
        # Return default settings on error
        return UserSettingsResponse(
            custom_instructions="",
            memory_count=0
        )


async def update_custom_instructions(user_id: str, instructions: str) -> CustomInstructionsResponse:
    """
    Update custom instructions for a user.

    Args:
        user_id: Unique identifier for the user
        instructions: New custom instructions text

    Returns
    -------
        CustomInstructionsResponse: Updated instructions and success status
    """
    try:
        memory_wrapper = get_memory_wrapper()

        success = await memory_wrapper.update_custom_instructions(user_id, instructions)

        if success:
            # Also add a memory entry about the instruction update
            try:
                await memory_wrapper.add_memory(
                    user_id=user_id,
                    content="Updated personal AI instructions",
                    metadata={
                        "interaction_type": "settings_update",
                        "setting_type": "custom_instructions",
                        "instructions_length": len(instructions),
                        "timestamp": "now"
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to log instruction update in memory: {e}")

        return CustomInstructionsResponse(
            instructions=instructions,
            updated=success
        )

    except Exception as e:
        logger.exception(f"Error updating custom instructions for {user_id}: {e}")
        return CustomInstructionsResponse(
            instructions=instructions,
            updated=False
        )


async def clear_user_memory(user_id: str) -> ClearMemoryResponse:
    """
    Clear all memories for a user.

    Args:
        user_id: Unique identifier for the user

    Returns
    -------
        ClearMemoryResponse: Success status and message
    """
    try:
        memory_wrapper = get_memory_wrapper()

        result = await memory_wrapper.delete_all_memories(user_id)

        if isinstance(result, dict) and "message" in result:
            message = result["message"]
        else:
            message = "All memories cleared successfully"

        return ClearMemoryResponse(
            cleared=True,
            message=message
        )

    except Exception as e:
        logger.exception(f"Error clearing memory for user {user_id}: {e}")
        return ClearMemoryResponse(
            cleared=False,
            message=f"Failed to clear memories: {e}"
        )
