import uuid

from fastapi import Request


def get_local_token_version_from_state(request: Request) -> int | None:
    """Read local token version from request state."""
    token_version = getattr(request.state, "local_token_version", None)
    if isinstance(token_version, int) and not isinstance(token_version, bool):
        return token_version
    return None


def get_local_session_id_from_state(request: Request) -> uuid.UUID | None:
    """Read local auth session ID from request state."""
    session_id = getattr(request.state, "local_session_id", None)
    if isinstance(session_id, uuid.UUID):
        return session_id
    return None


def get_user_id_from_state(request: Request) -> uuid.UUID | None:
    """Read authenticated user ID from request state."""
    user_id = getattr(request.state, "user_id", None)
    if isinstance(user_id, uuid.UUID):
        return user_id
    return None


def store_local_auth_state(
    request: Request,
    *,
    token_version: int,
    session_id: uuid.UUID | None,
) -> None:
    """Store validated local auth token metadata on request state."""
    request.state.local_token_version = token_version
    request.state.local_session_id = session_id


def store_user_id_on_request(request: Request, user_id: uuid.UUID) -> None:
    """Store authenticated user ID on request state."""
    request.state.user_id = user_id
