"""Authentication error handling middleware."""

import logging
from collections.abc import Callable

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.auth.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenExpiredError,
)


logger = logging.getLogger(__name__)


class AuthErrorMiddleware(BaseHTTPMiddleware):
    """Middleware to handle authentication errors gracefully."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process requests and handle auth errors."""
        try:
            return await call_next(request)
        except (AuthenticationError, InvalidTokenError, TokenExpiredError, InvalidCredentialsError) as exc:
            # Handle specific auth exceptions
            logger.warning(
                f"Authentication failed for {request.method} {request.url.path}: {exc.detail}",
                extra={
                    "client_host": request.client.host if request.client else "unknown",
                    "auth_error_type": type(exc).__name__,
                }
            )
            return JSONResponse(
                status_code=401,
                content={
                    "detail": exc.detail,
                    "error_code": "AUTH_REQUIRED",
                    "suggestions": [
                        "Ensure you are logged in",
                        "Check if your session has expired",
                        "Try logging in again",
                    ]
                }
            )
        except HTTPException as exc:
            # Handle other HTTP exceptions (403, etc.)
            if exc.status_code == 403:
                logger.warning(
                    f"Access forbidden for {request.method} {request.url.path}",
                    extra={
                        "client_host": request.client.host if request.client else "unknown",
                    }
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": exc.detail or "Access forbidden",
                        "error_code": "ACCESS_DENIED",
                    }
                )
            # Re-raise all other HTTP exceptions (including database errors that return 500)
            raise
        # REMOVED: The catch-all Exception handler that was masking database errors
