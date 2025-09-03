"""Security middleware."""

from collections.abc import Awaitable, Callable

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
upload_rate_limit = limiter.limit("20/minute")  # File uploads, video creation
ai_rate_limit = limiter.limit("50/minute")  # AI-powered operations
api_rate_limit = limiter.limit("100/minute")  # General API calls

# Rate limit dependencies for router-level application


def create_rate_limit_dependency(
    limit_decorator: Callable[[Callable], Callable],
) -> Callable[[Request], Awaitable[None]]:
    """Create rate limit dependencies from decorators.

    This allows applying rate limits at router level without modifying functions.
    """

    @limit_decorator
    async def rate_limited_dependency(request: Request) -> None:
        """Apply rate limiting to protect router endpoints."""

    return rate_limited_dependency


# Pre-configured dependencies for common use cases
books_rate_limit = create_rate_limit_dependency(api_rate_limit)
upload_route_limit = create_rate_limit_dependency(upload_rate_limit)
