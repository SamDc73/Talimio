"""Security middleware."""


import ipaddress
from functools import lru_cache

from fastapi import Request
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.config.settings import get_settings


@lru_cache(maxsize=32)
def _parse_trusted_proxy_networks(trusted_proxy_cidrs: str) -> tuple[ipaddress._BaseNetwork, ...]:
    """Parse trusted proxy CIDRs from settings, skipping invalid values."""
    networks: list[ipaddress._BaseNetwork] = []
    for raw_value in trusted_proxy_cidrs.split(","):
        cidr = raw_value.strip()
        if not cidr:
            continue
        try:
            network = ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            continue
        networks.append(network)
    return tuple(networks)


def _is_trusted_proxy(client_host: str, trusted_proxy_cidrs: str) -> bool:
    """Return whether the direct socket IP belongs to a trusted proxy range."""
    try:
        client_ip = ipaddress.ip_address(client_host)
    except ValueError:
        return False
    trusted_networks = _parse_trusted_proxy_networks(trusted_proxy_cidrs)
    return any(client_ip in network for network in trusted_networks)


def get_client_ip(request: Request) -> str:
    """Resolve the effective client IP with trusted-proxy-aware XFF handling."""
    client_host = request.client.host if request.client and request.client.host else ""
    if not client_host:
        return "unknown"

    trusted_proxy_cidrs = get_settings().TRUSTED_PROXY_CIDRS
    if not _is_trusted_proxy(client_host, trusted_proxy_cidrs):
        return client_host

    forwarded_for = request.headers.get("x-forwarded-for", "")
    for candidate in (part.strip() for part in forwarded_for.split(",")):
        if not candidate:
            continue
        try:
            ipaddress.ip_address(candidate)
        except ValueError:
            continue
        return candidate

    return client_host


_API_CSP_HEADER = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"


class SimpleSecurityMiddleware:
    """
    Ultra-simple security middleware.

    Adds essential headers and basic protection.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle HTTP response start events with security headers."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path", ""))

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["X-XSS-Protection"] = "1; mode=block"
                headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                self._set_api_headers(path, headers)

            await send(message)

        await self.app(scope, receive, send_with_security_headers)

    def _set_api_headers(self, path: str, headers: MutableHeaders) -> None:
        if path.startswith("/api/"):
            headers["Content-Security-Policy"] = _API_CSP_HEADER
        if path.startswith("/api/v1/auth/"):
            headers["Cache-Control"] = "no-store"
            headers["Pragma"] = "no-cache"
            headers["Expires"] = "0"
