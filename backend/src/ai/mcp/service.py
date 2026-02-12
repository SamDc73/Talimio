"""Service layer for user-managed MCP servers."""

from __future__ import annotations

import base64
import hashlib
import logging
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlparse
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Select, select

from src.ai.mcp.client import get_mcp_client, probe_mcp_server
from src.ai.mcp.config import MCPAuthConfig, MCPConfig, MCPServerConfig
from src.ai.mcp.schemas import AuthType, MCPServerCreateRequest
from src.config.settings import get_settings
from src.database.pagination import Paginator
from src.user.models import UserMCPServer


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)


def _token_cipher() -> Fernet:
    """Return a configured Fernet cipher for token encryption."""
    settings = get_settings()
    mcp_token_encryption_key = settings.MCP_TOKEN_ENCRYPTION_KEY
    if mcp_token_encryption_key and mcp_token_encryption_key.get_secret_value().strip():
        key_bytes = mcp_token_encryption_key.get_secret_value().encode("utf-8")
    else:
        auth_secret_key = settings.AUTH_SECRET_KEY.get_secret_value()
        digest = hashlib.sha256(auth_secret_key.encode("utf-8")).digest()
        key_bytes = base64.urlsafe_b64encode(digest)
    try:
        return Fernet(key_bytes)
    except ValueError as exc:
        msg = "MCP token encryption key must be a urlsafe base64-encoded string"
        raise ValueError(msg) from exc


def _encrypt_token(token: str | None) -> str | None:
    if not token:
        return None
    cipher = _token_cipher()
    return cipher.encrypt(token.encode("utf-8")).decode("utf-8")


def _decrypt_token(token: str | None) -> str | None:
    if not token:
        return None
    cipher = _token_cipher()
    try:
        decrypted = cipher.decrypt(token.encode("utf-8"))
    except InvalidToken:
        logger.warning("Failed to decrypt MCP auth token; skipping token for server")
        return None
    return decrypted.decode("utf-8")


def _encrypt_headers(headers: Mapping[str, str] | None) -> dict[str, str]:
    if not headers:
        return {}
    encrypted: dict[str, str] = {}
    for name, value in headers.items():
        encrypted_value = _encrypt_token(value)
        if encrypted_value:
            encrypted[name] = encrypted_value
    return encrypted


def _decrypt_headers(headers: Mapping[str, str] | None) -> dict[str, str]:
    if not headers:
        return {}
    decrypted: dict[str, str] = {}
    for name, value in headers.items():
        decrypted_value = _decrypt_token(value)
        if decrypted_value:
            decrypted[name] = decrypted_value
    return decrypted


def _sanitize_name(candidate: str) -> str:
    slug_chars: list[str] = []
    for char in candidate.lower():
        if char.isalnum() or char == "-":
            slug_chars.append(char)
        elif slug_chars and slug_chars[-1] != "-":
            slug_chars.append("-")
    normalized = "".join(slug_chars).strip("-")
    return normalized or "remote-mcp"


def _derive_unique_name(base_name: str, existing_names: set[str]) -> str:
    if base_name not in existing_names:
        return base_name
    counter = 2
    while True:
        candidate = f"{base_name}-{counter}"
        if candidate not in existing_names:
            return candidate
        counter += 1


def _build_select(user_id: UUID) -> Select:
    return select(UserMCPServer).where(UserMCPServer.user_id == user_id)


async def list_user_mcp_servers(session: AsyncSession, user_id: UUID) -> list[UserMCPServer]:
    """Return every MCP server owned by the specified user."""
    result = await session.scalars(_build_select(user_id))
    return list(result)


async def paginate_user_mcp_servers(
    session: AsyncSession,
    user_id: UUID,
    *,
    page: int,
    page_size: int,
) -> tuple[list[UserMCPServer], int]:
    """Return a single page of MCP servers along with the total count."""
    paginator = Paginator(page=page, limit=page_size)
    items, total = await paginator.paginate(session, _build_select(user_id))
    return items, total


async def create_user_mcp_server(
    session: AsyncSession,
    *,
    user_id: UUID,
    payload: MCPServerCreateRequest,
) -> UserMCPServer:
    """Persist a new MCP server entry for the given user.

    Probes the server to fetch its name from the MCP initialize response.
    """
    settings = get_settings()
    parsed = urlparse(str(payload.url))
    if settings.PLATFORM_MODE.lower() == "cloud" and parsed.hostname in {"localhost", "127.0.0.1"}:
        msg = "Local MCP servers are not allowed in cloud mode"
        raise ValueError(msg)

    # Build headers for probing (includes auth token if bearer)
    probe_headers = payload.resolved_static_headers()
    if payload.auth_type == "bearer" and payload.auth_token is not None:
        probe_headers["Authorization"] = f"Bearer {payload.auth_token.get_secret_value()}"

    # Probe server to get its name from initialize response
    try:
        server_info = await probe_mcp_server(str(payload.url), headers=probe_headers)
        base_name = _sanitize_name(server_info.name)
    except Exception as exc:
        logger.warning("Failed to probe MCP server at %s: %s", payload.url, exc)
        msg = f"Could not connect to MCP server: {exc}"
        raise ValueError(msg) from exc

    existing = await session.scalars(select(UserMCPServer.name).where(UserMCPServer.user_id == user_id))
    existing_names = set(existing)
    name = _derive_unique_name(base_name, existing_names)

    token_value: str | None = None
    if payload.auth_type == "bearer" and payload.auth_token is not None:
        token_value = payload.auth_token.get_secret_value()
    encrypted_token = _encrypt_token(token_value)

    encrypted_headers = _encrypt_headers(payload.resolved_static_headers())

    server = UserMCPServer(
        user_id=user_id,
        name=name,
        url=str(payload.url),
        auth_type=payload.auth_type,
        auth_token=encrypted_token,
        static_headers=encrypted_headers,
        enabled=payload.enabled,
    )
    session.add(server)
    await session.flush()
    await session.refresh(server)
    return server


async def delete_user_mcp_server(session: AsyncSession, *, user_id: UUID, server_id: UUID) -> bool:
    """Delete a server entry if it belongs to the user."""
    server = await session.get(UserMCPServer, server_id)
    if server is None or server.user_id != user_id:
        return False
    await session.delete(server)
    await session.flush()
    return True


def _to_mcp_config(server: UserMCPServer) -> MCPServerConfig:
    token = _decrypt_token(server.auth_token)
    auth = MCPAuthConfig(type=cast("AuthType", server.auth_type), token=token)
    decrypted_headers = _decrypt_headers(server.static_headers)
    data = {
        "name": server.name,
        "url": server.url,
        "auth": auth,
        "static_headers": decrypted_headers,
    }
    return MCPServerConfig.model_validate(data)


def build_user_mcp_config(user_servers: Iterable[UserMCPServer]) -> MCPConfig:
    """Build an MCP config that only contains the user's dynamic servers."""
    servers: dict[str, MCPServerConfig] = {}
    for server in user_servers:
        if not server.enabled:
            continue
        try:
            config = _to_mcp_config(server)
        except Exception as exc:
            logger.warning("Skipping invalid MCP server '%s': %s", server.name, exc)
            continue
        servers[config.name] = config
    return MCPConfig(servers=servers)


async def get_user_mcp_config(session: AsyncSession, user_id: UUID) -> MCPConfig:
    """Return a merged MCP config that includes a user's custom servers."""
    user_servers = await list_user_mcp_servers(session, user_id)
    return build_user_mcp_config(user_servers)


async def get_user_mcp_server(session: AsyncSession, *, user_id: UUID, server_name: str) -> MCPServerConfig | None:
    """Return the MCP server config for a user."""
    config = await get_user_mcp_config(session, user_id)
    return config.get(server_name)


async def list_user_mcp_tools(
    session: AsyncSession,
    *,
    user_id: UUID,
    server_name: str,
    config: MCPConfig | None = None,
) -> list[Any]:
    """List tools exposed by a user's MCP server via the shared client pool."""
    resolved_config = config or await get_user_mcp_config(session, user_id)
    client = get_mcp_client()
    return await client.list_tools(server_name, config=resolved_config)
