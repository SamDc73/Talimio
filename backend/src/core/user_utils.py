"""User ID resolution utilities for different deployment modes."""

from uuid import UUID

from src.auth.config import DEFAULT_USER_ID
from src.config.settings import get_settings


def resolve_user_id(provided_user_id: UUID | None = None) -> UUID:
    """
    Resolve the effective user ID based on deployment mode.

    For single-user mode (AUTH_PROVIDER="none"):
        - Always returns DEFAULT_USER_ID regardless of provided_user_id
        - This allows single-user mode to work without authentication

    For multi-user mode (AUTH_PROVIDER="supabase"):
        - Returns provided_user_id if present
        - Raises error if no user_id provided (requires authentication)

    Args:
        provided_user_id: User ID from authentication (None if not authenticated)

    Returns
    -------
        UUID: The effective user ID to use

    Raises
    ------
        ValueError: If multi-user mode but no user_id provided
    """
    settings = get_settings()

    if settings.AUTH_PROVIDER == "none":
        # Single-user mode: always use default user
        return DEFAULT_USER_ID

    # Multi-user mode: require authenticated user
    if provided_user_id is None:
        msg = "Authentication required in multi-user mode"
        raise ValueError(msg)

    return provided_user_id


def get_user_filter(provided_user_id: UUID | None = None) -> UUID:
    """
    Get the user ID for database filtering.

    This is a convenience function that wraps resolve_user_id.
    """
    return resolve_user_id(provided_user_id)
