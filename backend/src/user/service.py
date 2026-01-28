"""User service for handling user settings and memory management."""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.memory import add_memory, delete_memory, get_memories
from src.user.models import UserPreferences as UserPreferencesModel
from src.user.schemas import (
    CustomInstructionsResponse,
    PartialUserPreferences,
    PreferencesUpdateResponse,
    UserPreferences,
    UserSettingsResponse,
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

        # CRITICAL: Check user exists first to prevent foreign key violations
        from src.user.models import User

        user_check = await db_session.execute(
            select(User).where(User.id == user_uuid)
        )
        if not user_check.scalar_one_or_none():
            logger.error(f"User {user_uuid} not found in database - cannot save preferences")
            # Don't silently fail - this is a real error
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"User {user_uuid} not found")

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

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Failed to save preferences for user {user_id}: {e}")
        await db_session.rollback()
        # Check for foreign key violations
        if "foreign key violation" in str(e).lower() or "23503" in str(e):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"User {user_id} not found") from e
        return False


# User CRUD operations removed - Supabase auth handles user management
# Use auth.users table directly for user operations


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
        # Get user preferences from database (includes custom instructions)
        preferences = await _load_user_preferences(user_id, db_session)

        # Get custom instructions from preferences dict
        custom_instructions = ""
        if preferences.user_preferences:
            custom_instructions = preferences.user_preferences.get("custom_instructions", "")

        # Get memory count using direct function
        try:
            memories = await get_memories(user_id, limit=1000)
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


async def update_custom_instructions(
    user_id: UUID, instructions: str, db_session: AsyncSession
) -> CustomInstructionsResponse:
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
    from fastapi import HTTPException

    try:
        # Load current preferences
        preferences = await _load_user_preferences(user_id, db_session)

        # Update the custom instructions in user_preferences dict
        if preferences.user_preferences is None:
            preferences.user_preferences = {}
        preferences.user_preferences["custom_instructions"] = instructions

        # Save back to database - will raise HTTPException if user doesn't exist
        success = await _save_user_preferences(user_id, preferences, db_session)

        if success:
            # Also add a memory entry about the instruction update
            try:
                await add_memory(
                    user_id=user_id,
                    messages="Updated personal AI instructions",
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

    except HTTPException:
        # Re-raise HTTP exceptions (user not found, etc)
        raise
    except Exception as e:
        logger.exception(f"Error updating custom instructions for {user_id}: {e}")
        return CustomInstructionsResponse(instructions=instructions, updated=False)


async def get_user_memories(user_id: UUID, agent_id: str | None = None) -> list[dict]:
    """
    Get memories for a user, optionally filtered to a specific agent scope.

    Args:
        user_id: Unique identifier for the user
        agent_id: Limit results to memories created by a specific agent (optional)

    Returns
    -------
        List of memories with content, timestamps, and metadata
    """
    try:
        # Get all memories using direct function
        memories = await get_memories(user_id, limit=1000, agent_id=agent_id)

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
        return await delete_memory(user_id, memory_id)
    except Exception as e:
        logger.exception(f"Error deleting memory {memory_id} for user {user_id}: {e}")
        return False


async def update_user_preferences(
    user_id: UUID, partial_preferences: PartialUserPreferences, db_session: AsyncSession
) -> PreferencesUpdateResponse:
    """
    Update user preferences with partial updates.

    Args:
        user_id: Unique identifier for the user
        partial_preferences: Partial preferences to update
        db_session: Database session for saving preferences

    Returns
    -------
        PreferencesUpdateResponse: Updated preferences and success status
    """
    from fastapi import HTTPException

    try:
        # Load current preferences
        current_preferences = await _load_user_preferences(user_id, db_session)

        # Merge partial updates into current preferences
        updates = partial_preferences.model_dump(exclude_unset=True)
        merged_dict = current_preferences.model_dump()

        # Deep merge for nested user_preferences dict
        if "user_preferences" in updates and updates["user_preferences"] is not None:
            if merged_dict.get("user_preferences") is None:
                merged_dict["user_preferences"] = {}
            merged_dict["user_preferences"].update(updates["user_preferences"])
            del updates["user_preferences"]

        # Update other top-level fields
        merged_dict.update(updates)

        # Create new preferences object with merged data
        merged_preferences = UserPreferences(**merged_dict)

        # Save merged preferences - will raise HTTPException if user doesn't exist
        success = await _save_user_preferences(user_id, merged_preferences, db_session)
        return PreferencesUpdateResponse(preferences=merged_preferences, updated=success)
    except HTTPException:
        # Re-raise HTTP exceptions (user not found, etc)
        raise
    except Exception as e:
        logger.exception(f"Error updating preferences for user {user_id}: {e}")
        # Return current preferences on error
        current_prefs = await _load_user_preferences(user_id, db_session)
        return PreferencesUpdateResponse(preferences=current_prefs, updated=False)

