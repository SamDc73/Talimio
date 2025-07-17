"""User context utilities for single-user and multi-user deployments."""

from src.config.settings import get_settings


# Default user ID for single-user deployments
DEFAULT_SINGLE_USER_ID = "00000000-0000-0000-0000-000000000001"


def get_effective_user_id(current_user_id: str | None = None) -> str:
    """
    Get the effective user ID for the current request.

    This function handles both single-user (self-hosted) and multi-user (cloud) deployments:
    - Single-user: Returns a default user ID regardless of authentication
    - Multi-user: Returns the authenticated user's ID or raises an error

    Args:
        current_user_id: The authenticated user's ID (None if not authenticated)

    Returns
    -------
        str: The effective user ID to use for data operations

    Raises
    ------
        ValueError: If authentication is required but no user is provided
    """
    settings = get_settings()

    if settings.AUTH_DISABLED:
        # Single-user mode: use default user ID
        return DEFAULT_SINGLE_USER_ID
    # Multi-user mode: require authentication
    if current_user_id is None:
        raise ValueError("Authentication required but no user provided")
    return current_user_id


def get_user_filter_clause(current_user_id: str | None = None) -> dict:
    """
    Get the user filter clause for database queries.

    Returns a dictionary that can be used in SQLAlchemy where clauses.

    Args:
        current_user_id: The authenticated user's ID (None if not authenticated)

    Returns
    -------
        dict: Filter clause for user_id field
    """
    effective_user_id = get_effective_user_id(current_user_id)
    return {"user_id": effective_user_id}


def normalize_user_id_for_storage(current_user_id: str | None = None) -> str:
    """
    Normalize user ID for storage in database.

    This ensures consistent user ID handling across different deployment modes.

    Args:
        current_user_id: The authenticated user's ID (None if not authenticated)

    Returns
    -------
        str: The normalized user ID for storage
    """
    return get_effective_user_id(current_user_id)
