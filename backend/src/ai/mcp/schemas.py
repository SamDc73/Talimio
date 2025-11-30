"""Pydantic schemas for MCP server management."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlparse
from uuid import UUID

from pydantic import AliasChoices, AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr, field_validator


AuthType = Literal["none", "bearer"]


class MCPServerCreateRequest(BaseModel):
    """Schema for creating a user-managed MCP server."""

    url: AnyHttpUrl
    auth_type: AuthType = "none"
    auth_token: SecretStr | None = None
    static_headers: dict[str, SecretStr] | None = Field(
        default=None,
        validation_alias=AliasChoices("static_headers", "headers"),
        serialization_alias="headers",
        description="Static headers to send with every MCP request",
    )
    enabled: bool = True

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        parsed = urlparse(str(value))
        scheme = (parsed.scheme or "").lower()
        host = (parsed.hostname or "").lower()
        if scheme == "https":
            return value
        if scheme == "http" and host in {"localhost", "127.0.0.1", "::1"}:
            return value
        msg = "HTTP MCP servers are only allowed for localhost/127.0.0.1"
        raise ValueError(msg)

    @field_validator("auth_token")
    @classmethod
    def _validate_token(cls, token: SecretStr | None, info: Any) -> SecretStr | None:
        auth_type = info.data.get("auth_type", "none")
        if auth_type == "bearer":
            if token is None:
                msg = "Bearer auth requires auth_token"
                raise ValueError(msg)
            stripped = token.get_secret_value().strip()
            if not stripped:
                msg = "auth_token cannot be empty"
                raise ValueError(msg)
            return SecretStr(stripped)
        if token is not None:
            msg = "auth_token is only valid when auth_type is 'bearer'"
            raise ValueError(msg)
        return None

    @field_validator("static_headers")
    @classmethod
    def _validate_headers(cls, headers: dict[str, SecretStr] | None) -> dict[str, SecretStr] | None:
        if headers is None:
            return None
        normalized: dict[str, SecretStr] = {}
        for raw_name, secret in headers.items():
            name = (raw_name or "").strip()
            if not name:
                msg = "Header names cannot be empty"
                raise ValueError(msg)
            value = secret.get_secret_value().strip()
            if not value:
                msg = f"Header '{name}' value cannot be empty"
                raise ValueError(msg)
            normalized[name] = SecretStr(value)
        return normalized or None

    def resolved_static_headers(self) -> dict[str, str]:
        """Return sanitized static headers as plain strings."""
        if not self.static_headers:
            return {}
        return {name: secret.get_secret_value() for name, secret in self.static_headers.items()}


class MCPServerResponse(BaseModel):
    """Response payload for MCP server entries."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    url: AnyHttpUrl
    auth_type: AuthType
    headers: dict[str, str] = Field(default_factory=dict)
    enabled: bool
    has_token: bool
    created_at: datetime
    updated_at: datetime


class MCPServerListResponse(BaseModel):
    """Paginated MCP server collection."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[MCPServerResponse]
    total: int
    page: int
    per_page: int
