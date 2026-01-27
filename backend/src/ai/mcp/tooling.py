"""Helpers for exposing user MCP tools to the LLM client."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

from src.ai.mcp.client import get_mcp_client
from src.ai.mcp.config import MCPConfig
from src.ai.mcp.service import get_user_mcp_config, list_user_mcp_tools


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class MCPToolBinding:
    """Represents a tool exposed by a user's MCP server."""

    server_name: str
    tool_name: str
    description: str
    input_schema: dict[str, Any]
    encoded_name: str = ""

    def to_tool_schema(self) -> dict[str, Any]:
        """Return a LiteLLM-compatible tool schema."""
        schema = self.input_schema or {"type": "object", "properties": {}}
        return {
            "type": "function",
            "function": {
                "name": self.encoded_name or _slug_tool_name(self.server_name, self.tool_name),
                "description": self.description or f"{self.tool_name} via {self.server_name}",
                "parameters": schema,
            },
        }


async def load_user_tool_bindings(session: AsyncSession, user_id: UUID) -> list[MCPToolBinding]:
    """Load and normalize every MCP tool configured by the user."""
    config = await get_user_mcp_config(session, user_id)
    bindings: list[MCPToolBinding] = []
    for server in config.servers.values():
        try:
            tool_descriptors = await list_user_mcp_tools(
                session,
                user_id=user_id,
                server_name=server.name,
                config=config,
            )
        except Exception as exc:
            logger.warning("Failed to load MCP tools for server %s: %s", server.name, exc)
            continue
        for tool in tool_descriptors:
            name = _get_attr(tool, "name")
            if not name:
                continue
            description = _get_attr(tool, "description", "")
            schema = _coerce_schema(_get_attr(tool, "input_schema")) or _coerce_schema(_get_attr(tool, "inputSchema"))
            bindings.append(
                MCPToolBinding(
                    server_name=server.name,
                    tool_name=name,
                    description=str(description or ""),
                    input_schema=schema or {},
                )
            )
    return bindings


async def execute_user_tool_call(
    *,
    user_id: UUID,
    server_name: str,
    tool_name: str,
    encoded_name: str,
    arguments: dict[str, Any] | None,
    config: MCPConfig,
) -> Any:
    """Execute a user MCP tool and record preference stats.

    The config must be pre-loaded via get_user_mcp_config() before calling.
    This allows concurrent tool calls without database session conflicts.
    """
    logger.info(
        "Invoking MCP tool",
        extra={
            "mcp_server": server_name,
            "mcp_tool": tool_name,
            "encoded_tool": encoded_name,
            "user_id": str(user_id),
        },
    )
    client = get_mcp_client()
    try:
        result = await client.call_tool(
            server_name,
            tool_name=tool_name,
            arguments=arguments,
            config=config,
        )
    except Exception:
        logger.warning(
            "MCP tool failed",
            extra={
                "mcp_server": server_name,
                "mcp_tool": tool_name,
                "encoded_tool": encoded_name,
                "user_id": str(user_id),
            },
        )
        raise
    logger.info(
        "MCP tool completed",
        extra={
            "mcp_server": server_name,
            "mcp_tool": tool_name,
            "encoded_tool": encoded_name,
            "user_id": str(user_id),
        },
    )
    return result


def parse_tool_arguments(payload: dict[str, Any] | str | bytes | None) -> dict[str, Any]:
    """Normalize LiteLLM tool arguments into a dict."""
    if payload is None:
        return {}
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, (bytes, bytearray)):
        return parse_tool_arguments(payload.decode("utf-8"))
    if isinstance(payload, str):
        stripped = payload.strip()
        if not stripped:
            return {}
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            msg = f"Invalid tool arguments JSON: {exc.msg}"
            raise ValueError(msg) from exc
        if not isinstance(parsed, dict):
            msg = "Tool arguments payload must be a JSON object"
            raise TypeError(msg)
        return parsed
    msg = "Unsupported tool arguments payload type"
    raise TypeError(msg)


def build_tool_instruction(bindings: list[MCPToolBinding]) -> str | None:
    """Return a human-readable instruction describing available tools."""
    if not bindings:
        return None
    lines = [
        "You can call MCP tools to retrieve up-to-date references before writing content.",
        "Prefer calling a tool when the learner asks for recent sources, videos, or community input.",
    ]
    lines.extend(
        f"- {binding.tool_name} (server: {binding.server_name}): {binding.description}" for binding in bindings
    )
    return "\n".join(lines)


def _get_attr(obj: Any, name: str, default: Any | None = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _coerce_schema(schema: Any) -> dict[str, Any]:
    if schema is None:
        return {}
    if hasattr(schema, "model_dump"):
        schema = schema.model_dump()
    if not isinstance(schema, dict):
        return {}
    return schema


def _slug_tool_name(server_name: str, tool_name: str) -> str:
    base = f"{server_name}_{tool_name}".lower()
    return "".join(char if char.isalnum() or char == "_" else "_" for char in base)
