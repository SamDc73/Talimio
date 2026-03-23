"""Request-scoped tool execution runtime."""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any

from opentelemetry import trace

from src.ai.mcp.config import MCPConfig
from src.ai.mcp.tooling import execute_user_tool_call
from src.ai.tools.plan import LocalToolTarget, MCPToolTarget, ToolTarget


@dataclass(frozen=True, slots=True)
class PlannedToolCall:
    """Normalized model-emitted function call."""

    call_id: str
    name: str
    arguments: dict[str, Any] | str | bytes | None


@dataclass(frozen=True, slots=True)
class ExecutedToolCall:
    """Executed tool call payload ready to append to conversation."""

    call_id: str
    name: str
    content: str


async def execute_planned_tool_calls(
    *,
    calls: list[PlannedToolCall],
    tool_targets: dict[str, ToolTarget],
    user_id: uuid.UUID | None,
    mcp_config: MCPConfig | None,
    logger: logging.Logger,
) -> list[ExecutedToolCall]:
    """Execute a batch of model-emitted tool calls in parallel."""
    if not calls:
        return []

    formatted: list[ExecutedToolCall | None] = []
    pending: list[tuple[int, PlannedToolCall, ToolTarget, dict[str, Any]]] = []

    for index, call in enumerate(calls):
        target = tool_targets.get(call.name)
        if target is None:
            formatted.append(ExecutedToolCall(call_id=call.call_id, name=call.name, content=f"Error: Tool '{call.name}' is not available"))
            continue

        try:
            arguments = parse_tool_arguments(call.arguments)
        except (TypeError, ValueError) as error:
            formatted.append(ExecutedToolCall(call_id=call.call_id, name=call.name, content=f"Error: {error!s}"))
            continue

        formatted.append(None)
        pending.append((index, call, target, arguments))

    if pending:
        tasks = [
            _invoke_target(
                call=call,
                target=target,
                arguments=arguments,
                user_id=user_id,
                mcp_config=mcp_config,
            )
            for (_index, call, target, arguments) in pending
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for (index, call, _target, _arguments), result in zip(pending, results, strict=False):
            if isinstance(result, Exception):
                logger.error(
                    "ai.tool.failed",
                    extra={
                        "tool_name": call.name,
                        "tool_call_id": call.call_id,
                        "user_id": str(user_id) if user_id else None,
                        "error": str(result),
                    },
                )
                content = f"Error: {result!s}"
            else:
                content = format_tool_result(result)
            formatted[index] = ExecutedToolCall(call_id=call.call_id, name=call.name, content=content)

    return [entry for entry in formatted if entry is not None]


def parse_tool_arguments(payload: dict[str, Any] | str | bytes | None) -> dict[str, Any]:
    """Normalize function-call arguments into a dictionary."""
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
        except json.JSONDecodeError as error:
            msg = f"Invalid tool arguments JSON: {error.msg}"
            raise ValueError(msg) from error
        if not isinstance(parsed, dict):
            msg = "Tool arguments payload must be a JSON object"
            raise TypeError(msg)
        return parsed
    msg = "Unsupported tool arguments payload type"
    raise TypeError(msg)


def format_tool_result(result: Any) -> str:
    """Serialize tool output to the standard tool message string."""
    if isinstance(result, (dict, list)):
        try:
            return json.dumps(result, default=str)
        except (OverflowError, TypeError, ValueError):
            return str(result)
    return str(result)


async def _invoke_target(
    *,
    call: PlannedToolCall,
    target: ToolTarget,
    arguments: dict[str, Any],
    user_id: uuid.UUID | None,
    mcp_config: MCPConfig | None,
) -> Any:
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("llm.tool.execution") as span:
        span.set_attribute("llm.tool.name", call.name)
        span.set_attribute("llm.tool.call_id", call.call_id)
        if user_id is not None:
            span.set_attribute("enduser.id", str(user_id))

        if isinstance(target, LocalToolTarget):
            span.set_attribute("llm.tool.target_type", "local")
            return await target.execute(arguments)

        if not isinstance(target, MCPToolTarget):
            msg = f"Unknown tool target type for '{call.name}'"
            raise TypeError(msg)

        span.set_attribute("llm.tool.target_type", "mcp")
        span.set_attribute("llm.tool.server_name", target.server_name)
        span.set_attribute("llm.tool.encoded_name", call.name)
        span.set_attribute("llm.tool.target_name", target.tool_name)

        if user_id is None:
            msg = f"MCP tool '{call.name}' requires a user context"
            raise RuntimeError(msg)
        if mcp_config is None:
            msg = f"MCP tool '{call.name}' is unavailable because request MCP config is missing"
            raise RuntimeError(msg)

        return await execute_user_tool_call(
            user_id=user_id,
            server_name=target.server_name,
            tool_name=target.tool_name,
            encoded_name=call.name,
            arguments=arguments,
            config=mcp_config,
        )
