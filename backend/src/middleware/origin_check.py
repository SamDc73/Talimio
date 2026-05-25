"""Cross-origin protection for state-changing requests.

Replaces the legacy double-submit CSRF token middleware with a stateless
browser-derived check based on ``Sec-Fetch-Site`` plus an ``Origin`` allowlist
fallback. See ``auth_architecture_lock.md`` decisions #7-#11.

Decision logic for unsafe methods (POST/PUT/PATCH/DELETE):

* ``Sec-Fetch-Site`` is ``same-origin`` or ``same-site``: allow (modern browser
  declares the request is first-party for this registrable domain).
* Otherwise (``cross-site``, ``none``, missing header, legacy UA): the request
  is only allowed when the ``Origin`` header is present and matches the
  configured allowlist. This covers the dev case where Vite on
  ``localhost:5173`` calls the API on ``localhost:8080`` (different ports =
  ``cross-site`` per the origin spec).
* Anything else: 403 with structured warning log.

Safe methods (GET/HEAD/OPTIONS/TRACE) and explicitly exempt paths bypass the
check entirely.
"""


import logging
from collections.abc import Iterable

from fastapi import status
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send


logger = logging.getLogger(__name__)

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
_TRUSTED_FETCH_SITES = frozenset({"same-origin", "same-site"})


class OriginProtectionMiddleware:
    """Reject unsafe cross-site requests using Fetch Metadata + Origin allowlist."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        allowed_origins: Iterable[str],
        exempt_paths: Iterable[str] = (),
    ) -> None:
        self.app = app
        self._allowed_origins = frozenset(allowed_origins)
        self._exempt_paths = tuple(exempt_paths)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Reject the request when the browser cannot vouch for it as first-party."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        if request.method in _SAFE_METHODS or self._is_exempt(request.url.path):
            await self.app(scope, receive, send)
            return

        sec_fetch_site = request.headers.get("sec-fetch-site")
        if sec_fetch_site in _TRUSTED_FETCH_SITES:
            await self.app(scope, receive, send)
            return

        origin = request.headers.get("origin")
        if origin and origin in self._allowed_origins:
            await self.app(scope, receive, send)
            return

        logger.warning(
            "auth.origin_check.rejected",
            extra={
                "method": request.method,
                "path": request.url.path,
                "sec_fetch_site": sec_fetch_site or "",
                "origin": origin or "",
            },
        )
        response = PlainTextResponse("Cross-origin request blocked", status_code=status.HTTP_403_FORBIDDEN)
        await response(scope, receive, send)

    def _is_exempt(self, path: str) -> bool:
        return any(path.startswith(prefix) for prefix in self._exempt_paths)
