"""User service for handling user settings and memory management."""

import logging
import uuid

from psycopg.errors import ForeignKeyViolation
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import BadRequestError, NotFoundError
from src.memory import SlotCommitResult, advance_watermark_past_history, clear_slot, redact_slot_evidence, set_slot
from src.memory.models import UserProfileSlot, UserProfileSlotEvent
from src.user.models import UserPreferences as UserPreferencesModel
from src.user.schemas import (
    CustomInstructionsResponse,
    ProfileSlotItem,
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


async def _latest_applied_events(
    user_id: uuid.UUID, slots: list[str], db_session: AsyncSession
) -> dict[str, UserProfileSlotEvent]:
    """Most recent applied evidence event per slot (provenance for inferred values)."""
    if not slots:
        return {}
    stmt = (
        select(UserProfileSlotEvent)
        .where(
            UserProfileSlotEvent.user_id == user_id,
            UserProfileSlotEvent.slot.in_(slots),
            UserProfileSlotEvent.status == "applied",
        )
        .order_by(UserProfileSlotEvent.created_at.desc())
    )
    latest: dict[str, UserProfileSlotEvent] = {}
    for event in (await db_session.execute(stmt)).scalars():
        latest.setdefault(event.slot, event)
    return latest


async def get_user_memories(
    user_id: uuid.UUID, db_session: AsyncSession, *, limit: int = 100
) -> list[ProfileSlotItem]:
    """Return active profile slots, newest first, with provenance for inferred values."""
    stmt = (
        select(UserProfileSlot)
        .where(UserProfileSlot.user_id == user_id, UserProfileSlot.is_active.is_(True))
        .order_by(UserProfileSlot.updated_at.desc())
        .limit(limit)
    )
    rows = (await db_session.execute(stmt)).scalars().all()
    inferred_slots = [row.slot for row in rows if row.source == "inferred"]
    provenance = await _latest_applied_events(user_id, inferred_slots, db_session)

    memories: list[ProfileSlotItem] = []
    for row in rows:
        event = provenance.get(row.slot)
        memories.append(
            # model_validate: row.source is typed str; the schema's Literal
            # (DB CHECK-backed) is enforced by pydantic at this boundary.
            ProfileSlotItem.model_validate(
                {
                    "id": row.id,
                    "slot": row.slot,
                    "value": row.value,
                    "source": row.source,
                    "updated_at": row.updated_at,
                    "last_evidence_at": row.last_evidence_at,
                    "evidence_text": event.evidence_text if event is not None else None,
                    "source_message_id": event.message_id if event is not None else None,
                }
            )
        )
    return memories


async def set_profile_slot(user_id: uuid.UUID, slot: str, value: str, db_session: AsyncSession) -> SlotCommitResult:
    """Manually set a profile slot (manual values win over inferred ones)."""
    try:
        return await set_slot(db_session, user_id=user_id, slot=slot, value=value, source="manual")
    except ValueError as error:
        raise BadRequestError(str(error), feature_area="user") from error


async def clear_profile_slot(user_id: uuid.UUID, slot: str, db_session: AsyncSession, *, forget: bool) -> None:
    """Manually clear a slot; with forget=True also tombstone its raw evidence."""
    if forget:
        # Barrier first: blocks on the watermark row until any in-flight
        # maintenance job commits, so the clear below sees its writes.
        await advance_watermark_past_history(db_session, user_id=user_id)
    try:
        await clear_slot(db_session, user_id=user_id, slot=slot, source="manual")
    except ValueError as error:
        raise BadRequestError(str(error), feature_area="user") from error
    if forget:
        await redact_slot_evidence(db_session, user_id=user_id, slot=slot)


async def delete_user_memory(user_id: uuid.UUID, memory_id: str, db_session: AsyncSession) -> None:
    """
    Forget a specific profile-slot memory: deactivate it and tombstone its evidence.

    Args:
        user_id: Unique identifier for the user
        memory_id: The UserProfileSlot row id to forget
        db_session: Database session for the update

    """
    try:
        slot_id = uuid.UUID(memory_id)
    except ValueError as error:
        raise NotFoundError(MEMORY_RESOURCE_TYPE, memory_id, feature_area="user") from error

    # Barrier first: serialize with any in-flight maintenance job so the
    # deactivation below operates on its committed state.
    await advance_watermark_past_history(db_session, user_id=user_id)

    # Resolve the slot from the id without an is_active filter: an in-flight
    # job may have superseded the exact row the user saw; the intent is
    # "forget this slot", so the forget targets whatever row is active now.
    stmt = select(UserProfileSlot).where(
        UserProfileSlot.id == slot_id,
        UserProfileSlot.user_id == user_id,
    )
    row = (await db_session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise NotFoundError(MEMORY_RESOURCE_TYPE, memory_id, feature_area="user")

    await db_session.execute(
        update(UserProfileSlot)
        .where(
            UserProfileSlot.user_id == user_id,
            UserProfileSlot.slot == row.slot,
            UserProfileSlot.is_active.is_(True),
        )
        .values(is_active=False)
    )
    await redact_slot_evidence(db_session, user_id=user_id, slot=row.slot)
    await db_session.flush()


async def clear_user_memories(user_id: uuid.UUID, db_session: AsyncSession) -> None:
    """Forget all profile-slot memories: deactivate them and tombstone all evidence."""
    # Barrier first: blocks on the watermark row until any in-flight
    # maintenance job commits, so the deactivation below sees its writes.
    await advance_watermark_past_history(db_session, user_id=user_id)
    stmt = (
        update(UserProfileSlot)
        .where(UserProfileSlot.user_id == user_id, UserProfileSlot.is_active.is_(True))
        .values(is_active=False)
    )
    await db_session.execute(stmt)
    await redact_slot_evidence(db_session, user_id=user_id)
    await db_session.flush()
