"""User service for handling user settings and memory management."""

import logging
from uuid import UUID

from psycopg.errors import ForeignKeyViolation
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.memory import add_memory, delete_all_memories, delete_memory, get_memories
from src.user.models import UserPreferences as UserPreferencesModel
from src.user.schemas import (
    CustomInstructionsResponse,
    PartialUserPreferences,
    PreferencesUpdateResponse,
    UserPreferences,
    UserSettingsResponse,
)


logger = logging.getLogger(__name__)


class UserServiceError(Exception):
    """Base user-service domain exception."""


class UserNotFoundError(UserServiceError):
    """Raised when a user does not exist for a write operation."""


class UserPreferencesPersistenceError(UserServiceError):
    """Raised when user preferences cannot be persisted."""


class UserPreferencesLoadError(UserServiceError):
    """Raised when user preferences cannot be loaded."""


class UserMemoryAccessError(UserServiceError):
    """Raised when user memory operations fail."""


async def _load_user_preferences(user_id: UUID, db_session: AsyncSession) -> UserPreferences:
    """Load user preferences from database."""
    try:
        stmt = select(UserPreferencesModel).where(UserPreferencesModel.user_id == user_id)
        result = await db_session.execute(stmt)
        db_preferences = result.scalar_one_or_none()

        if db_preferences:
            return UserPreferences(**db_preferences.preferences)
        return UserPreferences()
    except (SQLAlchemyError, ValidationError, TypeError, ValueError) as error:
        logger.exception("Failed to load preferences for user %s", user_id)
        raise UserPreferencesLoadError from error


async def _save_user_preferences(user_id: UUID, preferences: UserPreferences, db_session: AsyncSession) -> bool:
    """Save user preferences to database."""
    # CRITICAL: Check user exists first to prevent foreign key violations.
    from src.user.models import User

    user_check = await db_session.execute(select(User).where(User.id == user_id))
    if not user_check.scalar_one_or_none():
        logger.warning("User %s not found in database - cannot save preferences", user_id)
        raise UserNotFoundError

    stmt = select(UserPreferencesModel).where(UserPreferencesModel.user_id == user_id)
    result = await db_session.execute(stmt)
    db_preferences = result.scalar_one_or_none()
    preferences_dict = preferences.model_dump()

    if db_preferences:
        db_preferences.preferences = preferences_dict
    else:
        db_preferences = UserPreferencesModel(user_id=user_id, preferences=preferences_dict)
        db_session.add(db_preferences)

    try:
        await db_session.flush()
    except IntegrityError as error:
        logger.warning("Failed to save preferences for user %s due to integrity error", user_id, exc_info=error)
        if isinstance(error.orig, ForeignKeyViolation):
            raise UserNotFoundError from error
        raise UserPreferencesPersistenceError from error
    except SQLAlchemyError as error:
        logger.exception("Failed to save preferences for user %s", user_id)
        raise UserPreferencesPersistenceError from error

    return True


# User CRUD operations removed - auth module handles user management
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
    preferences = await _load_user_preferences(user_id, db_session)
    custom_instructions = ""
    if preferences.user_preferences:
        custom_instructions = preferences.user_preferences.get("custom_instructions", "")

    memory_count = 0
    try:
        memories = await get_memories(user_id)
        memory_count = len(memories)
    except Exception:
        logger.warning("Failed to count memories for user %s", user_id, exc_info=True)

    return UserSettingsResponse(
        custom_instructions=custom_instructions,
        memory_count=memory_count,
        preferences=preferences,
    )


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
    try:
        # Load current preferences
        preferences = await _load_user_preferences(user_id, db_session)

        # Update the custom instructions in user_preferences dict
        if preferences.user_preferences is None:
            preferences.user_preferences = {}
        preferences.user_preferences["custom_instructions"] = instructions

        # Save back to database - raises typed domain exceptions on failure.
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
            except Exception:
                logger.warning("Failed to log instruction update in memory for user %s", user_id, exc_info=True)

        return CustomInstructionsResponse(instructions=instructions, updated=success)

    except UserServiceError:
        raise
    except Exception as error:
        logger.exception("Error updating custom instructions for %s", user_id)
        raise UserPreferencesPersistenceError from error


async def get_user_memories(user_id: UUID, agent_id: str | None = None, *, limit: int = 100) -> list[dict]:
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
        memories = await get_memories(user_id, limit=limit, agent_id=agent_id)
        formatted_memories = []
        for memory in memories:
            metadata = memory.get("metadata", {})
            formatted_memory = {
                "id": memory.get("id", ""),
                "content": memory.get("memory", ""),
                "timestamp": memory.get("created_at", ""),
                "metadata": metadata,
            }
            formatted_memories.append(formatted_memory)

        return formatted_memories

    except Exception as error:
        logger.exception("Error getting memories for user %s", user_id)
        raise UserMemoryAccessError from error


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
    except Exception as error:
        logger.exception("Error deleting memory %s for user %s", memory_id, user_id)
        raise UserMemoryAccessError from error


async def clear_user_memories(user_id: UUID, agent_id: str | None = None) -> bool:
    """Clear all memories for a user, optionally scoped to a specific agent."""
    try:
        return await delete_all_memories(user_id, agent_id=agent_id)
    except Exception as error:
        logger.exception("Error clearing memories for user %s", user_id)
        raise UserMemoryAccessError from error


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

        # Save merged preferences - raises typed domain exceptions on failure.
        success = await _save_user_preferences(user_id, merged_preferences, db_session)
        return PreferencesUpdateResponse(preferences=merged_preferences, updated=success)
    except UserServiceError:
        raise
    except Exception as error:
        logger.exception("Error updating preferences for user %s", user_id)
        raise UserPreferencesPersistenceError from error
