"""Auth-specific middleware: user injection and auth error handling.

Moves auth concerns under src/auth/ and provides reusable middleware classes.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware

from src.auth.config import get_user_id
from src.auth.context import is_auth_skip_path
from src.auth.exceptions import (
    AuthenticationError,
    InvalidTokenError,
    MissingTokenError,
    TokenExpiredError,
)
from src.middleware.error_handlers import handle_authentication_errors


if TYPE_CHECKING:
    from fastapi import Request, Response


logger = logging.getLogger(__name__)


class AuthInjectionMiddleware(BaseHTTPMiddleware):
    """Middleware that injects request.state.user_id for protected routes.

    Centralizes ownership of auth skip-path logic and user resolution.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request to inject user_id into request state for protected routes."""
        path = request.url.path

        # Skip authentication for configured paths or static files
        if is_auth_skip_path(path) or path.startswith("/static"):
            request.state.user_id = None
            return await call_next(request)

        # Protected routes: resolve user_id centrally
        try:
            request.state.user_id = await get_user_id(request)
            return await call_next(request)
        except (AuthenticationError, InvalidTokenError, MissingTokenError, TokenExpiredError) as e:
            # Return a consistent 401 response shape (exception handlers don't catch middleware errors)
            logger.exception("Auth error in middleware for %s: %s", path, type(e).__name__)
            return await handle_authentication_errors(request, e)
