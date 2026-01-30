"""HTTP MCP client utilities."""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol, cast

from src.ai.mcp.config import MCPConfig, MCPServerConfig


class MCPClientDependencyError(RuntimeError):
    """Raised when the MCP Python SDK is unavailable."""


class ClientSession(Protocol):
    """Minimal protocol for MCP client sessions."""

    async def call_tool(self, tool_name: str, *, arguments: dict[str, Any]) -> Any: ...

    async def list_tools(self) -> Any: ...

    async def initialize(self) -> Any: ...


_ClientSession: type[ClientSession] | None
_streamablehttp_client: Callable[..., Any] | None
_import_error: ModuleNotFoundError | None

try:
    mcp_module = importlib.import_module("mcp")
    streamable_module = importlib.import_module("mcp.client.streamable_http")
except ModuleNotFoundError as exc:
    _ClientSession = None
    _streamablehttp_client = None
    _import_error = exc
else:
    try:
        _ClientSession = cast("type[ClientSession]", mcp_module.ClientSession)
        _streamablehttp_client = cast("Callable[..., Any]", streamable_module.streamablehttp_client)
    except AttributeError as exc:
        _ClientSession = None
        _streamablehttp_client = None
        _import_error = ModuleNotFoundError(str(exc))
    else:
        _import_error = None


def _ensure_mcp_sdk() -> tuple[type[ClientSession], Callable[..., Any]]:
    if _ClientSession is None or _streamablehttp_client is None:
        msg = "The 'mcp' Python package is required for MCP client support. Install it with `uv pip install mcp`."
        raise MCPClientDependencyError(msg) from _import_error
    return _ClientSession, _streamablehttp_client


@dataclass
class MCPServerInfo:
    """Server metadata returned from MCP initialize."""

    name: str
    version: str


class MCPClient:
    """Thin asynchronous MCP client built on the official SDK."""

    def __init__(self, *, default_timeout: float = 10.0) -> None:
        self._default_timeout = default_timeout

    async def close(self) -> None:
        """Preserved for compatibility; sessions are created per call."""

    async def call_tool(
        self,
        server_name: str,
        *,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        call_timeout: float | None = None,
        config: MCPConfig | None = None,
    ) -> Any:
        """Call a remote MCP tool via streamable HTTP."""
        server = self._require_server(server_name, config=config)
        timeout_seconds = call_timeout or self._default_timeout
        payload = arguments or {}
        async with self._session(server) as session:
            try:
                return await asyncio.wait_for(
                    session.call_tool(tool_name, arguments=payload),
                    timeout=timeout_seconds,
                )
            except TimeoutError as exc:
                msg = f"MCP tool '{tool_name}' timed out after {timeout_seconds}s"
                raise TimeoutError(msg) from exc

    async def list_tools(self, server_name: str, *, config: MCPConfig | None = None) -> list[Any]:
        """Return tool metadata exposed by the server."""
        server = self._require_server(server_name, config=config)
        async with self._session(server) as session:
            response = await asyncio.wait_for(
                session.list_tools(),
                timeout=self._default_timeout,
            )
        tools = getattr(response, "tools", response)
        return list(tools or [])

    def _require_server(self, name: str, config: MCPConfig | None = None) -> MCPServerConfig:
        if config is None:
            msg = (
                "An MCPConfig instance is required when invoking MCPClient methods. "
                "Pass the per-user config returned by get_user_mcp_config so that "
                "servers are resolved dynamically from user-provided URLs."
            )
            raise MCPServerNotConfiguredError(msg)

        server = config.get(name)
        if server is None:
            msg = f"MCP server '{name}' is not registered in the provided config"
            raise MCPServerNotConfiguredError(msg)
        if not server.enabled:
            msg = f"MCP server '{name}' is disabled"
            raise MCPServerNotConfiguredError(msg)
        return server

    @asynccontextmanager
    async def _session(self, server: MCPServerConfig) -> AsyncIterator[ClientSession]:
        client_session_cls, http_client = _ensure_mcp_sdk()
        timeout = self._default_timeout
        async with (
            http_client(str(server.url), headers=server.headers()) as (read, write, _),
            client_session_cls(read, write) as session,
        ):
            try:
                await asyncio.wait_for(session.initialize(), timeout=timeout)
            except TimeoutError as exc:
                msg = f"MCP session initialization for '{server.name}' timed out after {timeout}s"
                raise TimeoutError(msg) from exc
            yield session


class MCPServerNotConfiguredError(RuntimeError):
    """Raised when a requested MCP server is not configured."""


async def probe_mcp_server(url: str, headers: dict[str, str] | None = None) -> MCPServerInfo:
    """Connect to an MCP server URL and return its metadata from initialize."""
    client_session_cls, http_client = _ensure_mcp_sdk()
    timeout = 10.0
    async with (
        http_client(url, headers=headers or {}) as (read, write, _),
        client_session_cls(read, write) as session,
    ):
        try:
            result = await asyncio.wait_for(session.initialize(), timeout=timeout)
        except TimeoutError as exc:
            msg = f"MCP server at '{url}' timed out during initialization"
            raise TimeoutError(msg) from exc
        server_info = result.serverInfo
        return MCPServerInfo(name=server_info.name, version=server_info.version)


@lru_cache(maxsize=1)
def _client_singleton() -> MCPClient:
    return MCPClient()


def get_mcp_client() -> MCPClient:
    """Return the shared MCP client instance."""
    return _client_singleton()


async def shutdown_mcp_client() -> None:
    """Close the shared MCP client (mostly for tests)."""
    if _client_singleton.cache_info().currsize == 0:
        return
    client = _client_singleton()
    await client.close()
    _client_singleton.cache_clear()


__all__ = [
    "MCPClient",
    "MCPClientDependencyError",
    "MCPServerInfo",
    "MCPServerNotConfiguredError",
    "get_mcp_client",
    "probe_mcp_server",
    "shutdown_mcp_client",
]
