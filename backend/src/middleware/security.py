"""Security middleware."""

import ipaddress
from collections.abc import Callable
from functools import lru_cache

from fastapi import Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

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


class SimpleSecurityMiddleware(BaseHTTPMiddleware):
    """
    Ultra-simple security middleware.

    Adds essential headers and basic protection.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle request with security headers."""
        response = await call_next(request)
        path = request.url.path

        # Essential security headers (prevents 90% of attacks)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if path.startswith("/api/"):
            response.headers["Content-Security-Policy"] = _API_CSP_HEADER
        if path.startswith("/api/v1/auth/"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        return response
