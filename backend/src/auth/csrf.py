"""CSRF token/cookie helpers shared by middleware wiring and auth routes."""


import http.cookies
import ipaddress
import secrets
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any
from urllib.parse import urlsplit

from fastapi import Response
from itsdangerous import URLSafeSerializer
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette_csrf import CSRFMiddleware

from src.auth.security import get_csrf_signing_key
from src.config.settings import get_settings


CSRF_COOKIE_NAME = "csrftoken"
CSRF_COOKIE_PATH = "/"
CSRF_COOKIE_SAMESITE = "lax"
CSRF_SERIALIZER_SALT = "csrftoken"
CSRF_COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days


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
        max_age=CSRF_COOKIE_MAX_AGE,
    )


class CSRFMiddlewareWithMaxAge(CSRFMiddleware):
    """CSRFMiddleware extended to set Max-Age on the CSRF cookie.

    starlette-csrf sets the cookie as a session cookie (no Max-Age), which
    causes it to disappear during extended browser/E2E sessions.  This subclass
    adds a ``cookie_max_age`` parameter so the cookie persists reliably.
    """

    def __init__(
        self,
        app: Any,
        secret: str,
        *,
        cookie_max_age: int | None = CSRF_COOKIE_MAX_AGE,
        **kwargs: Any,
    ) -> None:
        self.cookie_max_age = cookie_max_age
        super().__init__(app, secret, **kwargs)

    async def send(
        self,
        message: MutableMapping[str, Any],
        send: Callable[[MutableMapping[str, Any]], Awaitable[None]],
        scope: MutableMapping[str, Any],
    ) -> None:
        """Intercept response to set CSRF cookie with Max-Age when missing."""
        request = Request(scope)
        csrf_cookie = request.cookies.get(self.cookie_name)

        if csrf_cookie is None:
            message.setdefault("headers", [])
            headers = MutableHeaders(scope=message)

            cookie: http.cookies.BaseCookie = http.cookies.SimpleCookie()
            cookie_name = self.cookie_name
            cookie[cookie_name] = self._generate_csrf_token()
            cookie[cookie_name]["path"] = self.cookie_path
            cookie[cookie_name]["secure"] = self.cookie_secure
            cookie[cookie_name]["httponly"] = self.cookie_httponly
            cookie[cookie_name]["samesite"] = self.cookie_samesite
            if self.cookie_domain is not None:
                cookie[cookie_name]["domain"] = self.cookie_domain
            if self.cookie_max_age is not None:
                cookie[cookie_name]["max-age"] = str(self.cookie_max_age)
            headers.append("set-cookie", cookie.output(header="").strip())

        await send(message)
