"""Auth dependencies for user validation.

This module provides FastAPI dependencies for validating user existence
and ensuring proper user provisioning in the database.
"""

import logging
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import UserId
from src.database.session import get_db_session


logger = logging.getLogger(__name__)


async def valid_user_exists(
    user_id: UserId,
    db_session: AsyncSession = Depends(get_db_session),
) -> UUID:
    """Ensure user exists in profiles table.
    
    This dependency validates that a user profile exists before
    allowing operations that depend on it.
    
    Args:
        user_id: The authenticated user ID from auth dependency
        db_session: Database session
        
    Returns
    -------
        UUID: The validated user ID
        
    Raises
    ------
        HTTPException: 404 if user profile not found
    """
    try:
        # Check if user exists in profiles table
        result = await db_session.execute(
            text("SELECT 1 FROM public.profiles WHERE id = :user_id"),
            {"user_id": user_id}
        )

        if not result.scalar():
            logger.error(f"User profile {user_id} not found in database")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found",
            )

        return user_id

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error validating user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate user",
        ) from e


async def ensure_profile_exists(
    user_id: UserId,
    db_session: AsyncSession = Depends(get_db_session),
) -> UUID:
    """Create profile if it doesn't exist (idempotent).
    
    This dependency ensures a user profile exists, creating one
    if necessary. Useful for auto-provisioning users.
    
    Args:
        user_id: The authenticated user ID from auth dependency
        db_session: Database session
        
    Returns
    -------
        UUID: The user ID with guaranteed profile
    """
    try:
        # Try to create profile (will do nothing if exists)
        await db_session.execute(
            text("""
                INSERT INTO public.profiles (id, created_at, updated_at)
                VALUES (:user_id, NOW(), NOW())
                ON CONFLICT (id) DO NOTHING
            """),
            {"user_id": user_id}
        )
        await db_session.commit()

        return user_id

    except Exception as e:
        logger.exception(f"Error ensuring profile for user {user_id}: {e}")
        await db_session.rollback()
        # Don't fail - just return the user_id
        # The profile might already exist
        return user_id


async def validate_user_or_fail(
    user_id: UserId,
    db_session: AsyncSession = Depends(get_db_session),
) -> UUID:
    """Strict validation - fail if user doesn't exist in users table.
    
    This is for operations that absolutely require an existing user
    record and should not auto-provision.
    
    Args:
        user_id: The authenticated user ID from auth dependency
        db_session: Database session
        
    Returns
    -------
        UUID: The validated user ID
        
    Raises
    ------
        HTTPException: 404 if user not found in users table
    """
    try:
        from src.user.models import User

        # Check if user exists in users table (legacy)
        result = await db_session.execute(
            select(User).where(User.id == user_id)
        )

        if not result.scalar_one_or_none():
            logger.error(f"User {user_id} not found in users table")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        return user_id

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error validating user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate user",
        ) from e
