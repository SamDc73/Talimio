"""CSRF token/cookie helpers shared by middleware wiring and auth routes."""

import ipaddress
import secrets
from urllib.parse import urlsplit

from fastapi import Response
from itsdangerous import URLSafeSerializer

from src.auth.security import get_csrf_signing_key
from src.config.settings import get_settings


CSRF_COOKIE_NAME = "csrftoken"
CSRF_COOKIE_PATH = "/"
CSRF_COOKIE_SAMESITE = "lax"
CSRF_SERIALIZER_SALT = "csrftoken"


def get_csrf_cookie_domain(frontend_url: str) -> str | None:
    """Return a cookie domain that works for frontend/api subdomains when possible."""
    parsed = urlsplit(frontend_url)
    hostname = parsed.hostname
    if not hostname:
        return None
    if hostname in {"localhost", "127.0.0.1"}:
        return None
    try:
        ipaddress.ip_address(hostname)
        return None
    except ValueError:
        pass

    host_parts = hostname.split(".")
    if len(host_parts) < 2:
        return None
    return ".".join(host_parts[-2:])


def generate_csrf_token() -> str:
    """Generate a signed CSRF cookie value compatible with starlette-csrf."""
    serializer = URLSafeSerializer(get_csrf_signing_key(), CSRF_SERIALIZER_SALT)
    return serializer.dumps(secrets.token_urlsafe(128))


def set_csrf_cookie(response: Response) -> None:
    """Set/rotate CSRF cookie using the same policy as CSRFMiddleware."""
    settings = get_settings()
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=generate_csrf_token(),
        path=CSRF_COOKIE_PATH,
        domain=get_csrf_cookie_domain(settings.FRONTEND_URL),
        secure=settings.ENVIRONMENT == "production",
        httponly=False,
        samesite=CSRF_COOKIE_SAMESITE,
    )
