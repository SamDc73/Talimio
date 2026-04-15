"""User service for handling user settings and memory management."""

import logging
import uuid

from psycopg.errors import ForeignKeyViolation
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.memory import add_memory, delete_all_memories, delete_memory, get_memories
from src.exceptions import NotFoundError, UpstreamUnavailableError
from src.user.models import UserPreferences as UserPreferencesModel
from src.user.schemas import (
    CustomInstructionsResponse,
    UserPreferences,
    UserSettingsResponse,
)


logger = logging.getLogger(__name__)

USER_RESOURCE_TYPE = "user"
MEMORY_RESOURCE_TYPE = "memory"
MEMORY_SERVICE_UNAVAILABLE_DETAIL = "Memory service is unavailable"


async def _load_user_preferences(user_id: uuid.UUID, db_session: AsyncSession) -> UserPreferences:
    """Load user preferences from database."""
    try:
        stmt = select(UserPreferencesModel).where(UserPreferencesModel.user_id == user_id)
        result = await db_session.execute(stmt)
        db_preferences = result.scalar_one_or_none()

        if db_preferences:
            return UserPreferences(**db_preferences.preferences)
        return UserPreferences()
    except SQLAlchemyError:
        logger.exception("Failed to load preferences for user %s", user_id)
        raise
    except (PydanticValidationError, TypeError, ValueError) as error:
        logger.exception("Stored preferences are invalid for user %s", user_id)
        msg = "Stored user preferences are invalid"
        raise RuntimeError(msg) from error


async def _save_user_preferences(user_id: uuid.UUID, preferences: UserPreferences, db_session: AsyncSession) -> None:
    """Save user preferences to database."""
    # CRITICAL: Check user exists first to prevent foreign key violations.
    from src.user.models import User

    user_check = await db_session.execute(select(User).where(User.id == user_id))
    if not user_check.scalar_one_or_none():
        logger.warning("User %s not found in database - cannot save preferences", user_id)
        raise NotFoundError(USER_RESOURCE_TYPE, str(user_id), feature_area="user")

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
            raise NotFoundError(USER_RESOURCE_TYPE, str(user_id), feature_area="user") from error
        raise
    except SQLAlchemyError:
        logger.exception("Failed to save preferences for user %s", user_id)
        raise


# User CRUD operations removed - auth module handles user management
# Use auth.users table directly for user operations


async def get_user_settings(user_id: uuid.UUID, db_session: AsyncSession) -> UserSettingsResponse:
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
    except RuntimeError, TimeoutError, TypeError, ValueError:
        logger.warning("Failed to count memories for user %s", user_id, exc_info=True)

    return UserSettingsResponse(
        custom_instructions=custom_instructions,
        memory_count=memory_count,
        preferences=preferences,
    )


async def update_custom_instructions(
    user_id: uuid.UUID, instructions: str, db_session: AsyncSession
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
    # Load current preferences
    preferences = await _load_user_preferences(user_id, db_session)

    # Update the custom instructions in user_preferences dict
    if preferences.user_preferences is None:
        preferences.user_preferences = {}
    preferences.user_preferences["custom_instructions"] = instructions

    await _save_user_preferences(user_id, preferences, db_session)

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
    except RuntimeError, TimeoutError, TypeError, ValueError:
        logger.warning("Failed to log instruction update in memory for user %s", user_id, exc_info=True)

    return CustomInstructionsResponse(instructions=instructions, updated=True)


async def get_user_memories(user_id: uuid.UUID, agent_id: str | None = None, *, limit: int = 100) -> list[dict]:
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

    except (RuntimeError, TimeoutError, TypeError, ValueError) as error:
        logger.exception("Error getting memories for user %s", user_id)
        raise UpstreamUnavailableError(MEMORY_SERVICE_UNAVAILABLE_DETAIL, feature_area="user") from error


async def delete_user_memory(user_id: uuid.UUID, memory_id: str) -> None:
    """
    Delete a specific memory for a user.

    Args:
        user_id: Unique identifier for the user
        memory_id: The ID of the memory to delete

    """
    outcome = await delete_memory(user_id, memory_id)
    if outcome == "deleted":
        return
    if outcome == "not_found":
        raise NotFoundError(MEMORY_RESOURCE_TYPE, memory_id, feature_area="user")

    raise UpstreamUnavailableError(MEMORY_SERVICE_UNAVAILABLE_DETAIL, feature_area="user")


async def clear_user_memories(user_id: uuid.UUID, agent_id: str | None = None) -> None:
    """Clear all memories for a user, optionally scoped to a specific agent."""
    outcome = await delete_all_memories(user_id, agent_id=agent_id)
    if outcome == "cleared":
        return

    raise UpstreamUnavailableError(MEMORY_SERVICE_UNAVAILABLE_DETAIL, feature_area="user")
