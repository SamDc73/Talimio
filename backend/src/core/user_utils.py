"""User ID resolution utilities for different deployment modes."""

from uuid import UUID

from src.config.settings import get_settings


# Default user ID for single-user deployments
DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


def resolve_user_id(provided_user_id: UUID | None = None) -> UUID:
    """
    Resolve the effective user ID based on deployment mode.

    For self-hosted (AUTH_DISABLED=True):
        - Always returns DEFAULT_USER_ID regardless of provided_user_id
        - This allows single-user mode to work without authentication

    For cloud (AUTH_DISABLED=False):
        - Returns provided_user_id if present
        - Raises error if no user_id provided (requires authentication)

    Args:
        provided_user_id: User ID from authentication (None if not authenticated)

    Returns
    -------
        UUID: The effective user ID to use

    Raises
    ------
        ValueError: If cloud mode but no user_id provided
    """
    settings = get_settings()

    if settings.AUTH_DISABLED:
        # Self-hosted mode: always use default user
        return DEFAULT_USER_ID

    # Cloud mode: require authenticated user
    if provided_user_id is None:
        msg = "Authentication required in cloud mode"
        raise ValueError(msg)

    return provided_user_id


def get_user_filter(provided_user_id: UUID | None = None) -> UUID:
    """
    Get the user ID for database filtering.

    This is a convenience function that wraps resolve_user_id.
    """
    return resolve_user_id(provided_user_id)
