"""User service for handling user settings and memory management."""

import logging
import uuid

from psycopg.errors import ForeignKeyViolation
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import NotFoundError
from src.memory.models import UserProfileSlot
from src.user.models import UserPreferences as UserPreferencesModel
from src.user.schemas import (
    CustomInstructionsResponse,
    UserPreferences,
    UserSettingsResponse,
)


logger = logging.getLogger(__name__)

USER_RESOURCE_TYPE = "user"
MEMORY_RESOURCE_TYPE = "memory"


async def _load_user_preferences(user_id: uuid.UUID, db_session: AsyncSession) -> UserPreferences:
    """Load user preferences from database."""
    try:
        stmt = select(UserPreferencesModel).where(UserPreferencesModel.user_id == user_id)
        result = await db_session.execute(stmt)
        db_preferences = result.scalar_one_or_none()

        if db_preferences:
            return UserPreferences.model_validate(db_preferences.preferences)
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
    raw_custom_instructions = None
    if preferences.user_preferences:
        raw_custom_instructions = preferences.user_preferences.get("custom_instructions")
    custom_instructions = raw_custom_instructions if isinstance(raw_custom_instructions, str) else ""

    count_stmt = (
        select(func.count())
        .select_from(UserProfileSlot)
        .where(UserProfileSlot.user_id == user_id, UserProfileSlot.is_active.is_(True))
    )
    memory_count = (await db_session.execute(count_stmt)).scalar_one()

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

    return CustomInstructionsResponse(instructions=instructions, updated=True)


async def get_user_memories(user_id: uuid.UUID, db_session: AsyncSession, *, limit: int = 100) -> list[dict]:
    """
    Get active profile-slot memories for a user.

    Args:
        user_id: Unique identifier for the user
        db_session: Database session for reading profile slots
        limit: Maximum number of memories to return

    Returns
    -------
        List of memories with content, timestamps, and metadata
    """
    stmt = (
        select(UserProfileSlot)
        .where(UserProfileSlot.user_id == user_id, UserProfileSlot.is_active.is_(True))
        .order_by(UserProfileSlot.updated_at.desc())
        .limit(limit)
    )
    rows = (await db_session.execute(stmt)).scalars().all()

    return [
        {
            "id": str(row.id),
            "content": f"{row.slot}: {row.value}",
            "timestamp": row.updated_at.isoformat(),
            "metadata": {"slot": row.slot, "source": row.source},
        }
        for row in rows
    ]


async def delete_user_memory(user_id: uuid.UUID, memory_id: str, db_session: AsyncSession) -> None:
    """
    Delete (deactivate) a specific profile-slot memory for a user.

    Args:
        user_id: Unique identifier for the user
        memory_id: The UserProfileSlot row id to delete
        db_session: Database session for the update

    """
    try:
        slot_id = uuid.UUID(memory_id)
    except ValueError as error:
        raise NotFoundError(MEMORY_RESOURCE_TYPE, memory_id, feature_area="user") from error

    stmt = select(UserProfileSlot).where(
        UserProfileSlot.id == slot_id,
        UserProfileSlot.user_id == user_id,
        UserProfileSlot.is_active.is_(True),
    )
    row = (await db_session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise NotFoundError(MEMORY_RESOURCE_TYPE, memory_id, feature_area="user")

    row.is_active = False
    await db_session.flush()


async def clear_user_memories(user_id: uuid.UUID, db_session: AsyncSession) -> None:
    """Deactivate all active profile-slot memories for a user."""
    stmt = (
        update(UserProfileSlot)
        .where(UserProfileSlot.user_id == user_id, UserProfileSlot.is_active.is_(True))
        .values(is_active=False)
    )
    await db_session.execute(stmt)
    await db_session.flush()
