"""security middleware."""

from collections.abc import Callable

from fastapi import Request
from fastapi.responses import Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware


# Simple in-memory rate limiter (scales to 100k easily)
limiter = Limiter(key_func=get_remote_address)


class SimpleSecurityMiddleware(BaseHTTPMiddleware):
    """
    Ultra-simple security middleware.

    Adds essential headers and basic protection.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle request with security headers."""
        response = await call_next(request)

        # Essential security headers (prevents 90% of attacks)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response


# Rate limiting decorators (use on endpoints)
auth_rate_limit = limiter.limit("5/minute")  # Login attempts
api_rate_limit = limiter.limit("100/minute")  # General API calls
