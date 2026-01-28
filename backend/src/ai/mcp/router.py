"""API routes for managing user MCP servers."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import AnyHttpUrl, TypeAdapter

from src.ai.mcp.schemas import MCPServerCreateRequest, MCPServerListResponse, MCPServerResponse
from src.ai.mcp.service import (
    create_user_mcp_server,
    delete_user_mcp_server,
    paginate_user_mcp_servers,
)
from src.auth import CurrentAuth

router = APIRouter(prefix="/api/v1/mcp", tags=["mcp"])

_URL_ADAPTER = TypeAdapter(AnyHttpUrl)

def _coerce_url(raw: str) -> AnyHttpUrl:
    return _URL_ADAPTER.validate_python(raw)

def _serialize_server(server: Any) -> dict[str, Any]:
    """Serialize a stored MCP server into the API response shape."""
    url = str(_coerce_url(server.url))
    masked_headers = dict.fromkeys(server.static_headers or {}, "********")
    return {
        "id": server.id,
        "name": server.name,
        "url": url,
        "auth_type": server.auth_type,
        "headers": masked_headers,
        "enabled": server.enabled,
        "has_token": bool(server.auth_token),
        "created_at": server.created_at,
        "updated_at": server.updated_at,
    }

@router.get("/servers", response_model=MCPServerListResponse)
async def list_servers(
    auth: CurrentAuth,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
) -> dict[str, Any]:
    """Return all MCP servers configured by the authenticated user."""
    servers, total = await paginate_user_mcp_servers(auth.session, auth.user_id, page=page, page_size=page_size)
    return {
        "items": [_serialize_server(server) for server in servers],
        "total": total,
        "page": page,
        "per_page": page_size,
    }

@router.post("/servers", response_model=MCPServerResponse, status_code=status.HTTP_201_CREATED)
async def create_server(
    payload: MCPServerCreateRequest,
    auth: CurrentAuth,
) -> dict[str, Any]:
    """Create and persist a remote MCP server config for the user."""
    try:
        server = await create_user_mcp_server(auth.session, user_id=auth.user_id, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _serialize_server(server)

@router.delete("/servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(
    server_id: UUID,
    auth: CurrentAuth,
) -> None:
    """Remove a stored MCP server configuration."""
    deleted = await delete_user_mcp_server(auth.session, user_id=auth.user_id, server_id=server_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not found")
