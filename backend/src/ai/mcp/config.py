"""MCP server configuration helpers."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator


class MCPAuthConfig(BaseModel):
    """Authentication settings for an MCP server."""

    type: Literal["none", "bearer"] = "none"
    token: str | None = None

    @field_validator("token")
    @classmethod
    def _ensure_token_for_bearer(cls, token: str | None, info: Any) -> str | None:
        auth_type = info.data.get("type", "none")
        if auth_type == "bearer" and not token:
            msg = "Bearer auth requires a token"
            raise ValueError(msg)
        return token

    def headers(self) -> dict[str, str]:
        """Return HTTP headers for the configured auth."""
        if self.type == "bearer" and self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}


class MCPServerConfig(BaseModel):
    """Represents a single MCP server entry."""

    name: str
    url: AnyHttpUrl
    auth: MCPAuthConfig = Field(default_factory=MCPAuthConfig)
    static_headers: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True

    def headers(self) -> dict[str, str]:
        """Return auth headers derived from the server configuration."""
        headers = dict(self.auth.headers())
        headers.update(self.static_headers or {})
        return headers

    def cache_key(self) -> tuple[str, tuple[tuple[str, str], ...]]:
        """Stable cache key for client session pooling."""
        header_items = tuple(sorted(self.headers().items()))
        return str(self.url), header_items


class MCPConfig(BaseModel):
    """Aggregated MCP configuration."""

    servers: dict[str, MCPServerConfig] = Field(default_factory=dict)

    def get(self, name: str) -> MCPServerConfig | None:
        """Return the server config for the given name if present."""
        return self.servers.get(name)
