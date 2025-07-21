"""Authentication error handling middleware."""

import logging
from collections.abc import Callable

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


logger = logging.getLogger(__name__)


class AuthErrorMiddleware(BaseHTTPMiddleware):
    """Middleware to handle authentication errors gracefully."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process requests and handle auth errors."""
        try:
            response = await call_next(request)
            return response
        except HTTPException as exc:
            # Handle auth-related HTTP exceptions
            if exc.status_code == 401:
                logger.warning(
                    f"Authentication failed for {request.method} {request.url.path}",
                    extra={
                        "client_host": request.client.host if request.client else "unknown",
                        "headers": dict(request.headers),
                    }
                )
                return JSONResponse(
                    status_code=401,
                    content={
                        "detail": exc.detail or "Authentication required",
                        "error_code": "AUTH_REQUIRED",
                        "suggestions": [
                            "Ensure you are logged in",
                            "Check if your session has expired",
                            "Try logging in again",
                        ]
                    }
                )
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
            # Re-raise non-auth exceptions
            raise
        except Exception as e:
            # Log unexpected errors
            logger.exception(f"Unexpected error in request {request.method} {request.url.path}")

            # Check if it's an auth-related error
            error_str = str(e).lower()
            if any(auth_term in error_str for auth_term in ["auth", "token", "jwt", "credential"]):
                return JSONResponse(
                    status_code=401,
                    content={
                        "detail": "Authentication error occurred",
                        "error_code": "AUTH_ERROR",
                        "suggestions": [
                            "Check your authentication credentials",
                            "Ensure your API token is valid",
                            "Contact support if the issue persists",
                        ]
                    }
                )

            # Generic error response
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "error_code": "INTERNAL_ERROR",
                }
            )
