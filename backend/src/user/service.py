"""User service for handling user settings and memory management."""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.memory import get_memory_wrapper
from src.user.models import UserPreferences as UserPreferencesModel
from src.user.schemas import (
    ClearMemoryResponse,
    CustomInstructionsResponse,
    PreferencesUpdateResponse,
    UserCreate,
    UserPreferences,
    UserSettingsResponse,
    UserUpdate,
)


logger = logging.getLogger(__name__)


async def _load_user_preferences(user_id: UUID, db_session: AsyncSession) -> UserPreferences:
    """Load user preferences from database."""
    try:
        user_uuid = user_id
        stmt = select(UserPreferencesModel).where(UserPreferencesModel.user_id == user_uuid)
        result = await db_session.execute(stmt)
        db_preferences = result.scalar_one_or_none()

        if db_preferences:
            # Convert database JSONB to UserPreferences schema
            return UserPreferences(**db_preferences.preferences)

    except Exception as e:
        logger.warning(f"Failed to load preferences for user {user_id}: {e}")

    # Return default preferences if loading fails or no preferences exist
    return UserPreferences()


async def _save_user_preferences(user_id: UUID, preferences: UserPreferences, db_session: AsyncSession) -> bool:
    """Save user preferences to database."""
    try:
        user_uuid = user_id

        # Check if preferences already exist
        stmt = select(UserPreferencesModel).where(UserPreferencesModel.user_id == user_uuid)
        result = await db_session.execute(stmt)
        db_preferences = result.scalar_one_or_none()

        preferences_dict = preferences.model_dump()

        if db_preferences:
            # Update existing preferences
            db_preferences.preferences = preferences_dict
        else:
            # Create new preferences record
            db_preferences = UserPreferencesModel(user_id=user_uuid, preferences=preferences_dict)
            db_session.add(db_preferences)

        await db_session.commit()
        return True

    except Exception as e:
        logger.exception(f"Failed to save preferences for user {user_id}: {e}")
        await db_session.rollback()
        return False


async def create_user(user: UserCreate) -> dict:  # noqa: ARG001
    """Create a new user."""
    # For now, we'll just return a dummy user ID
    from uuid import uuid4
    return {"id": uuid4()}


async def get_user(user_id: UUID) -> dict:
    """Get a user by ID."""
    # For now, we'll just return a dummy user
    return {"id": user_id, "email": "test@example.com", "name": "Test User"}


async def update_user(user_id: UUID, user: UserUpdate) -> dict:
    """Update a user."""
    # For now, we'll just return the updated user
    return {"id": user_id, "email": user.email, "name": user.name}


async def delete_user(user_id: UUID) -> None:
    """Delete a user."""
    # For now, we'll just log the deletion
    logger.info(f"User {user_id} deleted.")


async def get_user_settings(user_id: UUID, db_session: AsyncSession) -> UserSettingsResponse:
    """
    Get user settings including custom instructions, memory count, and preferences.

    Args:
        user_id: Unique identifier for the user
        db_session: Database session for accessing user preferences

    Returns
    -------
        UserSettingsResponse: User's settings, memory information, and preferences
    """
    try:
        memory_manager = await get_memory_wrapper()

        # Get user preferences from database (includes custom instructions)
        preferences = await _load_user_preferences(user_id, db_session)

        # Get custom instructions from preferences dict
        custom_instructions = ""
        if preferences.user_preferences:
            custom_instructions = preferences.user_preferences.get("custom_instructions", "")

        # Get memory count using async method
        try:
            memories = await memory_manager.get_memories(user_id, limit=1000)
            memory_count = len(memories)
        except Exception as e:
            logger.warning(f"Failed to count memories for user {user_id}: {e}")
            memory_count = 0

        return UserSettingsResponse(
            custom_instructions=custom_instructions, memory_count=memory_count, preferences=preferences
        )

    except Exception as e:
        logger.exception(f"Error getting user settings for {user_id}: {e}")
        # Return default settings on error
        return UserSettingsResponse(custom_instructions="", memory_count=0, preferences=UserPreferences())


async def update_custom_instructions(user_id: UUID, instructions: str, db_session: AsyncSession) -> CustomInstructionsResponse:
    """
    Update custom instructions for a user.

    Args:
        user_id: Unique identifier for the user
        instructions: New custom instructions text
        db_session: Database session for saving preferences

    Returns
    -------
        CustomInstructionsResponse: Updated instructions and success status
    """
    try:
        # Load current preferences
        preferences = await _load_user_preferences(user_id, db_session)

        # Update the custom instructions in user_preferences dict
        if preferences.user_preferences is None:
            preferences.user_preferences = {}
        preferences.user_preferences["custom_instructions"] = instructions

        # Save back to database
        success = await _save_user_preferences(user_id, preferences, db_session)

        if success:
            # Also add a memory entry about the instruction update
            try:
                memory_wrapper = await get_memory_wrapper()
                await memory_wrapper.add_memory(
                    content="Updated personal AI instructions",
                    user_id=user_id,
                    metadata={
                        "interaction_type": "settings_update",
                        "setting_type": "custom_instructions",
                        "instructions_length": len(instructions),
                        "timestamp": "now",
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to log instruction update in memory: {e}")

        return CustomInstructionsResponse(instructions=instructions, updated=success)

    except Exception as e:
        logger.exception(f"Error updating custom instructions for {user_id}: {e}")
        return CustomInstructionsResponse(instructions=instructions, updated=False)


async def get_user_memories(user_id: UUID) -> list[dict]:
    """
    Get all memories for a user.

    Args:
        user_id: Unique identifier for the user

    Returns
    -------
        List of memories with content, timestamps, and metadata
    """
    try:
        memory_manager = await get_memory_wrapper()

        # Get all memories (retrieves all without search)
        memories = await memory_manager.get_memories(
            user_id=user_id,
            limit=1000,  # High limit to get all memories
        )

        # Format memories for web app consumption
        formatted_memories = []
        for memory in memories:
            metadata = memory.get("metadata", {})
            formatted_memory = {
                "id": memory.get("id", ""),  # Include ID for deletion
                "content": memory.get("memory", ""),
                "timestamp": memory.get("created_at", ""),
                "metadata": metadata,
            }
            formatted_memories.append(formatted_memory)

        return formatted_memories

    except Exception as e:
        logger.exception(f"Error getting memories for user {user_id}: {e}")
        return []


async def delete_user_memory(user_id: UUID, memory_id: str) -> bool:
    """
    Delete a specific memory for a user.

    Args:
        user_id: Unique identifier for the user
        memory_id: The ID of the memory to delete

    Returns
    -------
        bool: True if deletion was successful, False otherwise
    """
    try:
        memory_manager = await get_memory_wrapper()
        return await memory_manager.delete_memory(user_id, memory_id)
    except Exception as e:
        logger.exception(f"Error deleting memory {memory_id} for user {user_id}: {e}")
        return False


async def update_user_preferences(
    user_id: UUID, preferences: UserPreferences, db_session: AsyncSession
) -> PreferencesUpdateResponse:
    """
    Update user preferences.

    Args:
        user_id: Unique identifier for the user
        preferences: New preferences to save
        db_session: Database session for saving preferences

    Returns
    -------
        PreferencesUpdateResponse: Updated preferences and success status
    """
    try:
        success = await _save_user_preferences(user_id, preferences, db_session)
        return PreferencesUpdateResponse(preferences=preferences, updated=success)
    except Exception as e:
        logger.exception(f"Error updating preferences for user {user_id}: {e}")
        return PreferencesUpdateResponse(preferences=preferences, updated=False)


async def clear_user_memory(user_id: UUID) -> ClearMemoryResponse:
    """
    Clear all memories for a user.

    Args:
        user_id: Unique identifier for the user

    Returns
    -------
        ClearMemoryResponse: Success status and message
    """
    try:
        memory_manager = await get_memory_wrapper()

        # Use the optimized delete_all_memories method
        success = await memory_manager.delete_all_memories(user_id)

        message = "Successfully cleared all memories" if success else "Failed to clear memories"

        return ClearMemoryResponse(cleared=success, message=message)

    except Exception as e:
        logger.exception(f"Error clearing memory for user {user_id}: {e}")
        return ClearMemoryResponse(cleared=False, message=f"Failed to clear memories: {e}")
