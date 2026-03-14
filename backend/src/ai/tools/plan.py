"""Request-scoped tool planning for the LLM runtime."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


ToolExecutor = Callable[[dict[str, Any]], Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class LocalToolTarget:
    """Executable local-function tool target."""

    execute: ToolExecutor


@dataclass(frozen=True, slots=True)
class MCPToolTarget:
    """Executable MCP tool target."""

    server_name: str
    tool_name: str


ToolTarget = LocalToolTarget | MCPToolTarget


@dataclass(slots=True)
class FunctionToolDefinition:
    """Function tool schema plus an optional app-owned execution target."""

    schema: dict[str, Any]
    target: ToolTarget | None = None


@dataclass(frozen=True, slots=True)
class ModelRuntimeProfile:
    """Request-time model profile used for hosted-tool routing."""

    model: str
    supports_hosted_web_search: bool


@dataclass(slots=True)
class RequestToolPlan:
    """Single-request runtime tool plan consumed by LLMClient."""

    tool_schemas: list[dict[str, Any]] | None
    responses_tools: list[dict[str, Any]] | None
    tool_targets: dict[str, ToolTarget]
    tool_instruction: str | None
    default_tool_choice: str | None
    use_responses_transport: bool
    has_hosted_tools: bool


_SEARCH_PREFERENCE_INSTRUCTION = (
    "Search preference: use provider-native web search first when it is available and useful. "
    "Use local `web_search` when native search is unavailable, weak, or you need different sources."
)


def build_model_runtime_profile(model: str) -> ModelRuntimeProfile:
    """Return hosted-tool support profile for the selected model route."""
    normalized = model.strip().lower()
    supports_hosted_web_search = normalized.startswith("openai/")
    return ModelRuntimeProfile(model=model, supports_hosted_web_search=supports_hosted_web_search)


def build_request_tool_plan(
    *,
    model: str,
    explicit_tool_schemas: list[dict[str, Any]] | None,
    function_tools: list[FunctionToolDefinition],
    allowed_tools: set[str] | None,
    blocked_tools: set[str],
    include_hosted_web_search: bool,
) -> RequestToolPlan:
    """Assemble a request-scoped tool inventory and transport decision."""
    profile = build_model_runtime_profile(model)
    filtered_function_schemas: list[dict[str, Any]] = []
    tool_targets: dict[str, ToolTarget] = {}

    merged_definitions: list[FunctionToolDefinition] = []
    if explicit_tool_schemas:
        merged_definitions.extend(FunctionToolDefinition(schema=schema) for schema in explicit_tool_schemas)
    merged_definitions.extend(function_tools)

    for definition in merged_definitions:
        function_name = _extract_function_name(definition.schema)
        if function_name is None:
            continue
        name_key = function_name.lower()
        if allowed_tools is not None and name_key not in allowed_tools:
            continue
        if name_key in blocked_tools:
            continue
        filtered_function_schemas.append(definition.schema)
        if definition.target is not None:
            tool_targets[function_name] = definition.target

    has_hosted_tools = include_hosted_web_search and profile.supports_hosted_web_search
    responses_tools = list(filtered_function_schemas)
    if has_hosted_tools:
        responses_tools.append({"type": "web_search_preview"})

    use_responses_transport = has_hosted_tools
    effective_tools = responses_tools if use_responses_transport else filtered_function_schemas
    default_tool_choice = "auto" if effective_tools else None

    has_local_web_search = "web_search" in {name.lower() for name in tool_targets}
    tool_instruction = _SEARCH_PREFERENCE_INSTRUCTION if has_hosted_tools and has_local_web_search else None

    return RequestToolPlan(
        tool_schemas=filtered_function_schemas or None,
        responses_tools=responses_tools or None,
        tool_targets=tool_targets,
        tool_instruction=tool_instruction,
        default_tool_choice=default_tool_choice,
        use_responses_transport=use_responses_transport,
        has_hosted_tools=has_hosted_tools,
    )


def _extract_function_name(schema: dict[str, Any]) -> str | None:
    if not isinstance(schema, dict):
        return None
    function_block = schema.get("function")
    if not isinstance(function_block, dict):
        return None
    raw_name = function_block.get("name")
    if not isinstance(raw_name, str):
        return None
    normalized = raw_name.strip()
    return normalized or None
