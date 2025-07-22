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


async def _load_user_preferences(user_id: str, db_session: AsyncSession) -> UserPreferences:
    """Load user preferences from database."""
    try:
        user_uuid = UUID(user_id)
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


async def _save_user_preferences(user_id: str, preferences: UserPreferences, db_session: AsyncSession) -> bool:
    """Save user preferences to database."""
    try:
        user_uuid = UUID(user_id)

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
            db_preferences = UserPreferencesModel(
                user_id=user_uuid,
                preferences=preferences_dict
            )
            db_session.add(db_preferences)

        await db_session.commit()
        return True

    except Exception as e:
        logger.exception(f"Failed to save preferences for user {user_id}: {e}")
        await db_session.rollback()
        return False


async def create_user(_user: UserCreate) -> dict:
    """Create a new user."""
    # For now, we'll just return a dummy user ID
    return {"id": "a-fake-user-id"}


async def get_user(user_id: str) -> dict:
    """Get a user by ID."""
    # For now, we'll just return a dummy user
    return {"id": user_id, "email": "test@example.com", "name": "Test User"}


async def update_user(user_id: str, user: UserUpdate) -> dict:
    """Update a user."""
    # For now, we'll just return the updated user
    return {"id": user_id, "email": user.email, "name": user.name}


async def delete_user(user_id: str) -> None:
    """Delete a user."""
    # For now, we'll just log the deletion
    logger.info(f"User {user_id} deleted.")


async def get_user_settings(user_id: str, db_session: AsyncSession) -> UserSettingsResponse:
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
        memory_wrapper = get_memory_wrapper()

        # Get custom instructions
        custom_instructions = await memory_wrapper.get_custom_instructions(user_id)

        # Get memory count using dedicated method
        try:
            memory_count = await memory_wrapper.get_memory_count(user_id)
        except Exception as e:
            logger.warning(f"Failed to count memories for user {user_id}: {e}")
            memory_count = 0

        # Get user preferences from database
        preferences = await _load_user_preferences(user_id, db_session)

        return UserSettingsResponse(
            custom_instructions=custom_instructions, memory_count=memory_count, preferences=preferences
        )

    except Exception as e:
        logger.exception(f"Error getting user settings for {user_id}: {e}")
        # Return default settings on error
        return UserSettingsResponse(custom_instructions="", memory_count=0, preferences=UserPreferences())


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
                        "timestamp": "now",
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to log instruction update in memory: {e}")

        return CustomInstructionsResponse(instructions=instructions, updated=success)

    except Exception as e:
        logger.exception(f"Error updating custom instructions for {user_id}: {e}")
        return CustomInstructionsResponse(instructions=instructions, updated=False)


async def get_user_memories(user_id: str) -> list[dict]:
    """
    Get all memories for a user.

    Args:
        user_id: Unique identifier for the user

    Returns
    -------
        List of memories with content, timestamps, and metadata
    """
    try:
        memory_wrapper = get_memory_wrapper()

        # Search for all memories using empty query with allow_empty=True
        memories = await memory_wrapper.search_memories(
            user_id=user_id,
            query="",  # Empty query to get all memories
            limit=1000,  # High limit to get all memories
            relevance_threshold=0.0,  # Accept all relevance levels
            allow_empty=True,  # Allow empty query
        )

        # Format memories for web app consumption
        formatted_memories = []
        for memory in memories:
            formatted_memory = {
                "content": memory.get("memory", ""),
                "timestamp": memory.get("created_at", ""),
                "source": memory.get("source", "unknown"),
                "metadata": memory.get("metadata", {}),
            }
            formatted_memories.append(formatted_memory)

        return formatted_memories

    except Exception as e:
        logger.exception(f"Error getting memories for user {user_id}: {e}")
        return []


async def update_user_preferences(
    user_id: str, preferences: UserPreferences, db_session: AsyncSession
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

        return ClearMemoryResponse(cleared=True, message=message)

    except Exception as e:
        logger.exception(f"Error clearing memory for user {user_id}: {e}")
        return ClearMemoryResponse(cleared=False, message=f"Failed to clear memories: {e}")
