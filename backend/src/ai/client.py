import asyncio
import json
import logging
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, TypeVar

import litellm
from opentelemetry import trace
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai import AGENT_ID_ASSISTANT, AGENT_ID_DEFAULT
from src.ai.errors import (
    AIProviderError,
    AIRateLimitOrQuotaError,
    AIRuntimeError,
    AISchemaValidationError,
    AITimeoutError,
    AIToolExecutionError,
)
from src.ai.litellm_config import configure_litellm
from src.ai.mcp.config import MCPConfig
from src.ai.mcp.service import get_user_mcp_config
from src.ai.mcp.tooling import load_user_tool_bindings
from src.ai.models import (
    AdaptiveCourseStructure,
    CourseStructure,
    ExecutionPlan,
    LessonContent,
    SelfAssessmentQuiz,
)
from src.ai.prompts import (
    ADAPTIVE_COURSE_GENERATION_PROMPT,
    ADAPTIVE_PRACTICE_GRADING_PROMPT,
    COURSE_GENERATION_PROMPT,
    E2B_EXECUTION_SYSTEM_PROMPT,
    GRADING_COACH_PROMPT,
    LESSON_GENERATION_PROMPT,
    MEMORY_CONTEXT_SYSTEM_PROMPT,
    PRACTICE_GENERATION_PROMPT,
    PRACTICE_PREDICTION_PROMPT,
    SELF_ASSESSMENT_QUESTIONS_PROMPT,
)
from src.ai.tools.plan import (
    FunctionToolDefinition,
    MCPToolTarget,
    RequestToolPlan,
    ToolTarget,
    build_request_tool_plan,
)
from src.ai.tools.runtime import PlannedToolCall, execute_planned_tool_calls
from src.ai.tools.sandbox import SandboxToolContext, build_sandbox_function_tools
from src.ai.tools.search import build_web_search_function_tool
from src.config.settings import get_settings
from src.database.session import async_session_maker
from src.observability.log_context import get_log_context


configure_litellm()


T = TypeVar("T", bound=BaseModel)

_MAX_AUTONOMY_ROUNDS = 8
_MAX_STRUCTURED_GENERATION_ATTEMPTS = 2

_LITELLM_PROVIDER_ERROR_TYPES = (
    litellm.APIError,
    litellm.APIConnectionError,
    litellm.AuthenticationError,
    litellm.BadGatewayError,
    litellm.BadRequestError,
    litellm.BudgetExceededError,
    litellm.ContentPolicyViolationError,
    litellm.ContextWindowExceededError,
    litellm.InternalServerError,
    litellm.InvalidRequestError,
    litellm.NotFoundError,
    litellm.RouterRateLimitError,
    litellm.ServiceUnavailableError,
    litellm.UnprocessableEntityError,
    litellm.UnsupportedParamsError,
)

_COMPLETION_RUNTIME_ERROR_TYPES = (
    TimeoutError,
    asyncio.TimeoutError,
    ConnectionError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    ValidationError,
    litellm.RateLimitError,
    litellm.Timeout,
    litellm.JSONSchemaValidationError,
    litellm.APIResponseValidationError,
    *_LITELLM_PROVIDER_ERROR_TYPES,
)

_PARSE_COERCION_ERROR_TYPES = (TypeError, ValueError, ValidationError)
_MEMORY_OPERATION_ERROR_TYPES = (ImportError, *_COMPLETION_RUNTIME_ERROR_TYPES)
_GENERATION_WRAPPER_ERROR_TYPES = (
    AIRuntimeError,
    TimeoutError,
    asyncio.TimeoutError,
    ConnectionError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
_LEARNING_TOOL_NAMES = {
    "search_lessons",
    "list_relevant_courses",
    "get_course_state",
    "get_course_outline_state",
    "get_lesson_state",
    "get_course_frontier",
    "create_course",
    "append_course_lesson",
    "extend_lesson_with_context",
    "regenerate_lesson_with_context",
}
_LEARNING_INTENT_KEYWORDS = (
    "create course",
    "new course",
    "append lesson",
    "add lesson",
    "extend lesson",
    "regenerate lesson",
    "course state",
    "course outline",
    "lesson state",
    "course frontier",
    "relevant course",
    "search lesson",
    "find lesson",
)


@dataclass(slots=True)
class _LLMRequest:
    """Internal request contract consumed by the shared orchestration pipeline."""

    messages: list[dict[str, Any]]
    response_model: type[BaseModel] | None
    temperature: float | None
    tools: list[dict[str, Any]] | None
    sandbox_context: SandboxToolContext | None
    tool_choice: str | None
    user_id: uuid.UUID | None
    model: str
    num_retries: int | None
    max_completion_tokens: int | None
    stream: bool
    metadata: dict[str, Any] | None = None
    tool_schemas: list[dict[str, Any]] | None = None
    responses_tools: list[dict[str, Any]] | None = None
    tool_targets: dict[str, ToolTarget] = field(default_factory=dict)
    mcp_config: MCPConfig | None = None
    use_responses_transport: bool = False
    has_hosted_tools: bool = False
    tool_plan: RequestToolPlan | None = None


def _iter_exception_chain(error: Exception, max_depth: int = 6) -> list[Exception]:
    """Return the exception chain (cause/context) up to max_depth."""
    chain: list[Exception] = []
    current: Exception | None = error
    depth = 0
    while current is not None and depth < max_depth:
        chain.append(current)
        next_error = current.__cause__ if current.__cause__ is not None else current.__context__
        if not isinstance(next_error, Exception):
            break
        current = next_error
        depth += 1
    return chain


def _contains_rate_limit_or_quota_hint(error: Exception) -> bool:
    for current in _iter_exception_chain(error):
        lowered = str(current).lower()
        if "insufficient_quota" in lowered:
            return True
        if "ratelimiterror" in lowered:
            return True
        if "rate limit" in lowered:
            return True
        if "quota" in lowered and "exceed" in lowered:
            return True
    return False


def _contains_timeout_hint(error: Exception) -> bool:
    for current in _iter_exception_chain(error):
        lowered = str(current).lower()
        if "timeout" in lowered or "timed out" in lowered:
            return True
    return False


class LLMClient:
    """Manages LLM completion requests with memory and tool integration."""

    def __init__(self, agent_id: str = AGENT_ID_DEFAULT) -> None:
        """Initialize LLMClient.

        Args:
            agent_id: Logical identifier for the caller so memories can be scoped per module.
        """
        self._logger = logging.getLogger(__name__)
        self._agent_id = agent_id
        self._tool_filters = self._parse_tool_filters()
        self._background_tasks: set[asyncio.Task[Any]] = set()

    @asynccontextmanager
    async def _mcp_session(self) -> AsyncGenerator[AsyncSession]:
        """Return a short-lived DB session for MCP tooling.

        MCP tooling may need a DB session to load user configuration and tool bindings. If we reuse the
        request-scoped session, we risk keeping a database transaction open across long-running LLM calls,
        which shows up as "idle in transaction" (and can be especially painful with transaction poolers).
        """
        async with async_session_maker() as session:
            yield session

    def _parse_tool_filters(self) -> tuple[set[str] | None, set[str]]:
        settings = get_settings()
        allowed_env = settings.AI_ENABLED_TOOLS
        allowed = {token.strip().lower() for token in allowed_env.split(",") if token.strip()} if allowed_env else None
        blocked_env = settings.AI_DISABLED_TOOLS
        blocked = {token.strip().lower() for token in blocked_env.split(",") if token.strip()} if blocked_env else set()
        return allowed, blocked

    def _build_request(
        self,
        *,
        messages: list[dict[str, Any]],
        response_model: type[BaseModel] | None,
        temperature: float | None,
        tools: list[dict[str, Any]] | None,
        sandbox_context: SandboxToolContext | None,
        tool_choice: str | None,
        user_id: str | uuid.UUID | None,
        model: str | None,
        num_retries: int | None,
        max_completion_tokens: int | None,
        stream: bool,
        metadata: dict[str, Any] | None,
    ) -> _LLMRequest:
        settings = get_settings()
        return _LLMRequest(
            messages=list(messages),
            response_model=response_model,
            temperature=temperature,
            tools=tools,
            sandbox_context=sandbox_context,
            tool_choice=tool_choice,
            user_id=self._normalize_user_id(user_id),
            model=model or settings.primary_llm_model,
            num_retries=num_retries,
            max_completion_tokens=max_completion_tokens,
            stream=stream,
            metadata=metadata,
        )

    def _map_runtime_error(self, error: Exception, *, default_message: str) -> AIRuntimeError:
        if isinstance(error, AIRuntimeError):
            return error

        for current in _iter_exception_chain(error):
            if isinstance(current, litellm.RateLimitError) or _contains_rate_limit_or_quota_hint(current):
                return AIRateLimitOrQuotaError("LLM provider quota or rate limit reached")

            if isinstance(current, (litellm.Timeout, TimeoutError, asyncio.TimeoutError)) or _contains_timeout_hint(
                current
            ):
                return AITimeoutError("LLM request timed out")

            if isinstance(
                current, (ValidationError, litellm.JSONSchemaValidationError, litellm.APIResponseValidationError)
            ):
                return AISchemaValidationError("Structured response failed schema validation")

            if isinstance(current, _LITELLM_PROVIDER_ERROR_TYPES):
                return AIProviderError(default_message)

        return AIProviderError(default_message)

    def _log_runtime_error(self, error: AIRuntimeError, *, operation: str) -> None:
        if isinstance(error, (AIRateLimitOrQuotaError, AITimeoutError)):
            self._logger.warning("%s failed: %s (%s)", operation, error, error.category.value)
            return
        self._logger.error("%s failed: %s (%s)", operation, error, error.category.value)

    def _extract_latest_user_text(self, conversation: list[dict[str, Any]]) -> str:
        for message in reversed(conversation):
            if message.get("role") != "user":
                continue

            content = message.get("content")
            if isinstance(content, str):
                return content.strip()
            if not isinstance(content, list):
                return ""

            text_parts: list[str] = []
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") != "text":
                    continue
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    text_parts.append(text.strip())
            return " ".join(text_parts).strip()

        return ""

    def _looks_like_learning_intent(self, user_text: str) -> bool:
        lowered = user_text.lower()
        return any(keyword in lowered for keyword in _LEARNING_INTENT_KEYWORDS)

    def _log_learning_capability_turn(
        self,
        *,
        tool_targets: dict[str, ToolTarget],
        used_tool_names: set[str],
        conversation: list[dict[str, Any]],
        user_id: uuid.UUID | None,
        phase: str,
    ) -> None:
        available_learning_tools = sorted(name for name in tool_targets if name in _LEARNING_TOOL_NAMES)
        if not available_learning_tools:
            return

        used_learning_tools = sorted(name for name in used_tool_names if name in _LEARNING_TOOL_NAMES)
        user_text = self._extract_latest_user_text(conversation)
        should_use = self._looks_like_learning_intent(user_text) if user_text else False

        if used_learning_tools:
            self._logger.info(
                "learning_capability.turn.used",
                extra={
                    "phase": phase,
                    "user_id": str(user_id) if user_id else None,
                    "used_tools": used_learning_tools,
                    "available_tools": available_learning_tools,
                },
            )
            return

        self._logger.info(
            "learning_capability.turn.not_used",
            extra={
                "phase": phase,
                "user_id": str(user_id) if user_id else None,
                "available_tools": available_learning_tools,
                "should_use": should_use,
            },
        )
        if should_use:
            self._logger.warning(
                "learning_capability.turn.missed_opportunity",
                extra={
                    "phase": phase,
                    "user_id": str(user_id) if user_id else None,
                    "available_tools": available_learning_tools,
                },
            )

    async def _assemble_request_context(self, request: _LLMRequest) -> None:
        """Ordered context assembly: normalize -> memory -> tools."""
        if request.user_id is not None:
            request.messages = await self._inject_memory_into_messages(request.messages, request.user_id)

        request.tool_plan = await self._build_request_tool_plan(request)
        request.tool_schemas = request.tool_plan.tool_schemas
        request.responses_tools = request.tool_plan.responses_tools
        request.tool_targets = request.tool_plan.tool_targets
        request.use_responses_transport = request.tool_plan.use_responses_transport
        request.has_hosted_tools = request.tool_plan.has_hosted_tools
        request.tool_choice = request.tool_choice or request.tool_plan.default_tool_choice

        if request.tool_plan.tool_instruction:
            request.messages = self._inject_tool_instruction(request.messages, request.tool_plan.tool_instruction)

    async def _build_request_tool_plan(self, request: _LLMRequest) -> RequestToolPlan:
        function_tools: list[FunctionToolDefinition] = []
        if request.sandbox_context is not None:
            function_tools.extend(build_sandbox_function_tools(request.sandbox_context))

        settings = get_settings()
        exa_api_key = settings.EXA_API_KEY.get_secret_value() if settings.EXA_API_KEY is not None else ""
        web_search_tool = build_web_search_function_tool(
            api_key=exa_api_key,
            timeout_seconds=settings.EXA_SEARCH_TIMEOUT_SECONDS,
            default_max_results=settings.EXA_SEARCH_MAX_RESULTS,
        )
        if web_search_tool is not None:
            function_tools.append(web_search_tool)

        if settings.AI_ENABLE_EXPERIMENTAL_MCP_TOOLS and request.user_id is not None:
            mcp_tools, mcp_config = await self._load_mcp_tool_definitions(request.user_id)
            function_tools.extend(mcp_tools)
            request.mcp_config = mcp_config
        else:
            request.mcp_config = None

        if request.user_id is not None and self._agent_id == AGENT_ID_ASSISTANT:
            from src.ai.tools.learning import build_learning_action_tools, build_learning_query_tools

            function_tools.extend(build_learning_query_tools(user_id=request.user_id))
            function_tools.extend(build_learning_action_tools(user_id=request.user_id))

        return build_request_tool_plan(
            model=request.model,
            explicit_tool_schemas=request.tools,
            function_tools=function_tools,
            allowed_tools=self._tool_filters[0],
            blocked_tools=self._tool_filters[1],
            include_hosted_web_search=self._should_include_hosted_web_search(request),
        )

    def _should_include_hosted_web_search(self, request: _LLMRequest) -> bool:
        settings = get_settings()
        if not settings.AI_ENABLE_HOSTED_WEB_SEARCH:
            return False
        if request.stream:
            return False
        return request.response_model is None

    async def _load_mcp_tool_definitions(self, user_id: uuid.UUID) -> tuple[list[FunctionToolDefinition], MCPConfig]:
        async with self._mcp_session() as session:
            bindings = await load_user_tool_bindings(session, user_id)
            config = await get_user_mcp_config(session, user_id)

        definitions: list[FunctionToolDefinition] = []
        counts: dict[str, int] = {}
        for binding in bindings:
            tool_key = binding.tool_name.lower()
            if not self._is_tool_enabled(tool_key):
                continue

            base_name = self._slug_tool_key(binding.server_name, binding.tool_name)
            count = counts.get(base_name, 0) + 1
            counts[base_name] = count
            encoded_name = base_name if count == 1 else f"{base_name}_{count}"

            schema = {
                "type": "function",
                "function": {
                    "name": encoded_name,
                    "description": binding.description or f"{binding.tool_name} via {binding.server_name}",
                    "parameters": binding.input_schema or {"type": "object", "properties": {}},
                },
            }
            definitions.append(
                FunctionToolDefinition(
                    schema=schema,
                    target=MCPToolTarget(server_name=binding.server_name, tool_name=binding.tool_name),
                )
            )
        return definitions, config

    def _is_tool_enabled(self, tool_name: str) -> bool:
        normalized = tool_name.strip().lower()
        if not normalized:
            return False
        allowed, blocked = self._tool_filters
        if allowed is not None and normalized not in allowed:
            return False
        return normalized not in blocked

    def _inject_tool_instruction(self, messages: list[dict[str, Any]], instruction: str) -> list[dict[str, Any]]:
        if not instruction:
            return messages
        tool_message = {"role": "system", "content": instruction}
        if messages and messages[0].get("role") == "system":
            return [messages[0], tool_message, *messages[1:]]
        return [tool_message, *messages]

    def _handle_background_task_done(self, task: asyncio.Task[Any]) -> None:
        self._background_tasks.discard(task)
        if task.cancelled():
            return
        error = task.exception()
        if error is None:
            return
        self._logger.error("ai.background_task.failed", exc_info=(type(error), error, error.__traceback__))

    def _schedule_memory_save(self, user_id: uuid.UUID | None, messages: list[dict[str, Any]], response: Any) -> None:
        if user_id is None:
            return
        task = asyncio.create_task(self._save_conversation_to_memory(user_id, messages, response))
        self._background_tasks.add(task)
        task.add_done_callback(self._handle_background_task_done)

    def _extract_provider_name(self, model: str) -> str:
        normalized_model = model.strip()
        if "/" not in normalized_model:
            return "unknown"
        provider = normalized_model.split("/", 1)[0].strip()
        if not provider:
            return "unknown"
        return provider

    def _collect_tool_names(self, tools: list[dict[str, Any]] | None) -> list[str]:
        if not tools:
            return []

        names: list[str] = []
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            tool_type = tool.get("type")
            if tool_type == "function":
                function_payload = tool.get("function")
                if isinstance(function_payload, dict):
                    tool_name = function_payload.get("name")
                    if isinstance(tool_name, str) and tool_name.strip():
                        names.append(tool_name.strip())
                        continue
            if isinstance(tool_type, str) and tool_type.strip():
                names.append(tool_type.strip())
        return names

    def _current_trace_id(self) -> str | None:
        current_span = trace.get_current_span()
        get_span_context = getattr(current_span, "get_span_context", None)
        if not callable(get_span_context):
            return None
        span_context = get_span_context()
        if not span_context.is_valid:
            return None
        return f"{span_context.trace_id:032x}"

    def _build_completion_metadata(  # noqa: C901, PLR0912
        self,
        *,
        metadata: dict[str, Any] | None,
        model: str,
        tools: list[dict[str, Any]] | None,
        user_id: str | uuid.UUID | None,
        settings: Any,
    ) -> dict[str, Any]:
        merged: dict[str, Any] = dict(metadata or {})
        context = get_log_context()

        generation_name = merged.get("generation_name")
        if not isinstance(generation_name, str) or not generation_name.strip():
            merged["generation_name"] = f"{self._agent_id}_generation"

        trace_id = self._current_trace_id()
        if trace_id and not merged.get("trace_id"):
            merged["trace_id"] = trace_id

        session_id = context.get("session_id")
        if session_id and not merged.get("session_id"):
            merged["session_id"] = str(session_id)

        normalized_user_id: str | None = None
        if user_id is not None:
            normalized_user_id = str(user_id)
        elif context.get("user_id"):
            normalized_user_id = str(context["user_id"])
        if normalized_user_id:
            if not merged.get("trace_user_id"):
                merged["trace_user_id"] = normalized_user_id
            if not merged.get("user_id"):
                merged["user_id"] = normalized_user_id

        if context.get("course_id") and not merged.get("course_id"):
            merged["course_id"] = str(context["course_id"])

        feature_area = context.get("feature_area")
        if feature_area and not merged.get("feature_area"):
            merged["feature_area"] = str(feature_area)

        if not merged.get("model_name"):
            merged["model_name"] = model
        if not merged.get("provider_name"):
            merged["provider_name"] = self._extract_provider_name(model)

        tool_names = self._collect_tool_names(tools)
        if tool_names and not merged.get("tool_names"):
            merged["tool_names"] = tool_names

        existing_tags = merged.get("tags")
        tags: list[str] = []
        if isinstance(existing_tags, list):
            tags = [str(tag) for tag in existing_tags if str(tag).strip()]
        elif isinstance(existing_tags, str) and existing_tags.strip():
            tags = [existing_tags.strip()]

        default_tags = [f"platform_mode:{settings.PLATFORM_MODE}"]
        if feature_area:
            default_tags.append(f"feature_area:{feature_area}")
        for tag in default_tags:
            if tag not in tags:
                tags.append(tag)
        if tags:
            merged["tags"] = tags

        return merged

    def _record_response_observability_fields(self, response: Any, *, tool_names: list[str]) -> None:
        span = trace.get_current_span()
        if not span.is_recording():
            return

        if tool_names:
            span.set_attribute("llm.tool_names", json.dumps(tool_names))

        usage = getattr(response, "usage", None)
        if usage is None and isinstance(response, dict):
            usage = response.get("usage")
        prompt_tokens: Any = None
        completion_tokens: Any = None
        total_tokens: Any = None
        if isinstance(usage, dict):
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            total_tokens = usage.get("total_tokens")
        elif usage is not None:
            prompt_tokens = getattr(usage, "prompt_tokens", None)
            completion_tokens = getattr(usage, "completion_tokens", None)
            total_tokens = getattr(usage, "total_tokens", None)

        if isinstance(prompt_tokens, int):
            span.set_attribute("llm.prompt_tokens", prompt_tokens)
        if isinstance(completion_tokens, int):
            span.set_attribute("llm.completion_tokens", completion_tokens)
        if isinstance(total_tokens, int):
            span.set_attribute("llm.total_tokens", total_tokens)

        hidden_params = getattr(response, "_hidden_params", None)
        if hidden_params is None and isinstance(response, dict):
            hidden_params = response.get("_hidden_params")
        if isinstance(hidden_params, dict):
            response_cost = hidden_params.get("response_cost")
            if isinstance(response_cost, (int, float)):
                span.set_attribute("llm.cost_usd", float(response_cost))

    async def complete(  # noqa: C901, PLR0912
        self,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
        user_id: str | uuid.UUID | None = None,
        response_format: Any | None = None,
        extra_body: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        stream: bool = False,
        model: str | None = None,
        num_retries: int | None = None,
        max_completion_tokens: int | None = None,
        parallel_tool_calls: bool = False,
        use_responses_transport: bool = False,
        previous_response_id: str | None = None,
    ) -> Any:
        """Low-level completion method using LiteLLM directly."""
        try:
            settings = get_settings()
            request_model = model or settings.primary_llm_model
            tool_names = self._collect_tool_names(tools)

            common_kwargs: dict[str, Any] = {"model": request_model, "timeout": settings.ai_request_timeout}
            if user_id:
                common_kwargs["user"] = str(user_id)
            if stream:
                common_kwargs["stream"] = stream
            if num_retries is not None:
                common_kwargs["num_retries"] = num_retries
            if max_completion_tokens is not None:
                common_kwargs["max_completion_tokens"] = max_completion_tokens
                common_kwargs["max_tokens"] = max_completion_tokens
            if tools and parallel_tool_calls:
                common_kwargs["parallel_tool_calls"] = True
            if temperature is not None:
                common_kwargs["temperature"] = temperature
            if tool_choice:
                common_kwargs["tool_choice"] = tool_choice
            if tools:
                common_kwargs["tools"] = tools
            if extra_body is not None:
                common_kwargs["extra_body"] = extra_body
            completion_metadata = self._build_completion_metadata(
                metadata=metadata,
                model=request_model,
                tools=tools,
                user_id=user_id,
                settings=settings,
            )
            if completion_metadata:
                common_kwargs["metadata"] = completion_metadata

            if use_responses_transport:
                response_kwargs = dict(common_kwargs)
                response_kwargs["input"] = messages
                if previous_response_id is not None:
                    response_kwargs["previous_response_id"] = previous_response_id
                response = await asyncio.wait_for(litellm.responses(**response_kwargs), timeout=settings.ai_request_timeout)
                if not stream:
                    self._record_response_observability_fields(response, tool_names=tool_names)
                return response

            completion_kwargs = dict(common_kwargs)
            completion_kwargs["messages"] = messages
            if response_format is not None:
                completion_kwargs["response_format"] = response_format
            response = await asyncio.wait_for(litellm.acompletion(**completion_kwargs), timeout=settings.ai_request_timeout)
            if not stream:
                self._record_response_observability_fields(response, tool_names=tool_names)
            return response

        except _COMPLETION_RUNTIME_ERROR_TYPES as error:
            mapped = self._map_runtime_error(error, default_message="Model completion failed")
            self._log_runtime_error(mapped, operation="Model completion")
            raise mapped from error

    async def get_completion(
        self,
        messages: list[dict[str, Any]],
        response_model: type[BaseModel] | None = None,
        temperature: float | None = None,
        tools: list[dict[str, Any]] | None = None,
        sandbox_context: SandboxToolContext | None = None,
        tool_choice: str | None = None,
        user_id: str | uuid.UUID | None = None,
        model: str | None = None,
        num_retries: int | None = None,
        max_completion_tokens: int | None = None,
        stream: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        """Shared execution engine for free-form and structured generation."""
        request = self._build_request(
            messages=messages,
            response_model=response_model,
            temperature=temperature,
            tools=tools,
            sandbox_context=sandbox_context,
            tool_choice=tool_choice,
            user_id=user_id,
            model=model,
            num_retries=num_retries,
            max_completion_tokens=max_completion_tokens,
            stream=stream,
            metadata=metadata,
        )

        if request.response_model and request.stream:
            msg = "Streaming is not supported for structured outputs"
            raise ValueError(msg)

        try:
            await self._assemble_request_context(request)

            if request.stream:
                return self._stream_unstructured_completion(
                    messages=request.messages,
                    temperature=request.temperature,
                    tools=request.tool_schemas,
                    tool_choice=request.tool_choice,
                    user_id=request.user_id,
                    model=request.model,
                    num_retries=request.num_retries,
                    tool_targets=request.tool_targets,
                    mcp_config=request.mcp_config,
                    metadata=request.metadata,
                )

            if request.response_model is None and request.use_responses_transport:
                result, conversation = await self._run_responses_autonomy_loop(request)
            elif request.response_model is None:
                result, conversation = await self._run_autonomy_loop(request)
            else:
                result, conversation = await self._run_structured_completion_with_retries(request)
            self._schedule_memory_save(request.user_id, conversation, result)
            return result

        except ValueError:
            raise
        except AIRuntimeError:
            raise
        except _COMPLETION_RUNTIME_ERROR_TYPES as error:
            mapped = self._map_runtime_error(error, default_message="Completion failed")
            self._log_runtime_error(mapped, operation="Completion")
            raise mapped from error

    async def _run_structured_completion_with_retries(self, request: _LLMRequest) -> tuple[Any, list[dict[str, Any]]]:
        """Retry full structured generation from the original request on contract/schema failure."""
        last_error: AISchemaValidationError | None = None

        for attempt in range(1, _MAX_STRUCTURED_GENERATION_ATTEMPTS + 1):
            try:
                return await self._run_autonomy_loop(request)
            except AISchemaValidationError as error:
                last_error = error
                self._logger.warning(
                    "Structured generation validation failed on attempt %s/%s: %s",
                    attempt,
                    _MAX_STRUCTURED_GENERATION_ATTEMPTS,
                    error,
                )
                if attempt >= _MAX_STRUCTURED_GENERATION_ATTEMPTS:
                    raise

        if last_error is not None:
            raise last_error

        msg = "Structured response failed schema validation"
        raise AISchemaValidationError(msg)

    async def _run_autonomy_loop(self, request: _LLMRequest) -> tuple[Any, list[dict[str, Any]]]:
        """Run the shared non-stream autonomy loop for structured and free-form calls."""
        conversation = list(request.messages)
        tool_round = 0
        used_tool_names_in_turn: set[str] = set()

        while True:
            tool_round += 1
            if tool_round > _MAX_AUTONOMY_ROUNDS:
                msg = f"Tool autonomy loop exceeded {_MAX_AUTONOMY_ROUNDS} rounds"
                raise AIToolExecutionError(msg)

            effective_tool_choice = request.tool_choice

            response_format: dict[str, Any] | None = None
            if request.response_model is not None:
                should_enforce_provider_schema = effective_tool_choice in (None, "none") or not request.tool_schemas
                if should_enforce_provider_schema:
                    response_format = self._build_response_format(request.response_model)

            response = await self.complete(
                messages=conversation,
                temperature=request.temperature,
                tools=request.tool_schemas,
                tool_choice=effective_tool_choice,
                user_id=request.user_id,
                metadata=request.metadata,
                response_format=response_format,
                model=request.model,
                num_retries=request.num_retries,
                max_completion_tokens=request.max_completion_tokens,
                parallel_tool_calls=bool(request.tool_schemas),
            )

            assistant_message = response.choices[0].message
            assistant_content = assistant_message.content or ""
            tool_calls = getattr(assistant_message, "tool_calls", None)

            if tool_calls:
                normalized_tool_calls = self._normalize_chat_tool_calls(tool_calls)
                used_tool_names_in_turn.update(call.name for call in normalized_tool_calls)
                await self._append_tool_calls(
                    conversation,
                    assistant_content=assistant_content,
                    tool_calls=tool_calls,
                    user_id=request.user_id,
                    tool_targets=request.tool_targets,
                    mcp_config=request.mcp_config,
                )
                continue

            self._log_learning_capability_turn(
                tool_targets=request.tool_targets,
                used_tool_names=used_tool_names_in_turn,
                conversation=conversation,
                user_id=request.user_id,
                phase="chat_completions",
            )
            conversation.append({"role": "assistant", "content": assistant_content})
            if request.response_model is None:
                return assistant_content, conversation

            try:
                parsed = self._coerce_response_model(response, request.response_model)
                return parsed, conversation
            except _PARSE_COERCION_ERROR_TYPES as parse_error:
                msg = "Structured response failed schema validation"
                raise AISchemaValidationError(msg) from parse_error

    async def _run_responses_autonomy_loop(self, request: _LLMRequest) -> tuple[str, list[dict[str, Any]]]:
        """Run the non-stream autonomy loop using LiteLLM Responses transport."""
        conversation = list(request.messages)
        response_input = list(request.messages)
        previous_response_id: str | None = None
        tool_round = 0
        used_tool_names_in_turn: set[str] = set()

        while True:
            tool_round += 1
            if tool_round > _MAX_AUTONOMY_ROUNDS:
                msg = f"Tool autonomy loop exceeded {_MAX_AUTONOMY_ROUNDS} rounds"
                raise AIToolExecutionError(msg)

            response = await self.complete(
                messages=response_input,
                temperature=request.temperature,
                tools=request.responses_tools,
                tool_choice=request.tool_choice,
                user_id=request.user_id,
                metadata=request.metadata,
                model=request.model,
                num_retries=request.num_retries,
                max_completion_tokens=request.max_completion_tokens,
                parallel_tool_calls=bool(request.responses_tools),
                use_responses_transport=True,
                previous_response_id=previous_response_id,
            )

            assistant_content = self._extract_responses_text(response)
            function_calls = self._extract_responses_function_calls(response)
            if function_calls:
                used_tool_names_in_turn.update(call.name for call in function_calls)
                executed_calls = await execute_planned_tool_calls(
                    calls=function_calls,
                    tool_targets=request.tool_targets,
                    user_id=request.user_id,
                    mcp_config=request.mcp_config,
                    logger=self._logger,
                )
                if assistant_content:
                    conversation.append({"role": "assistant", "content": assistant_content})
                response_input = [
                    {
                        "type": "function_call_output",
                        "call_id": executed_call.call_id,
                        "output": executed_call.content,
                    }
                    for executed_call in executed_calls
                ]
                conversation.extend(
                    {
                        "role": "tool",
                        "tool_call_id": executed_call.call_id,
                        "name": executed_call.name,
                        "content": executed_call.content,
                    }
                    for executed_call in executed_calls
                )
                previous_response_id = self._extract_responses_response_id(response)
                if previous_response_id is None:
                    msg = "Responses transport returned tool calls without response id"
                    raise AIToolExecutionError(msg)
                continue

            self._log_learning_capability_turn(
                tool_targets=request.tool_targets,
                used_tool_names=used_tool_names_in_turn,
                conversation=conversation,
                user_id=request.user_id,
                phase="responses",
            )
            conversation.append({"role": "assistant", "content": assistant_content})
            return assistant_content, conversation

    def _extract_responses_response_id(self, response: Any) -> str | None:
        response_id = self._read_attr_or_key(response, "id")
        if isinstance(response_id, str) and response_id.strip():
            return response_id
        return None

    def _extract_responses_function_calls(self, response: Any) -> list[PlannedToolCall]:
        output_items = self._extract_responses_output_items(response)
        calls: list[PlannedToolCall] = []
        for item in output_items:
            item_type = self._read_attr_or_key(item, "type")
            if item_type != "function_call":
                continue
            call_id = self._read_attr_or_key(item, "call_id")
            if not isinstance(call_id, str) or not call_id.strip():
                fallback = self._read_attr_or_key(item, "id")
                if isinstance(fallback, str) and fallback.strip():
                    call_id = fallback
            name = self._read_attr_or_key(item, "name")
            arguments = self._read_attr_or_key(item, "arguments")
            if not isinstance(call_id, str) or not call_id.strip():
                continue
            if not isinstance(name, str) or not name.strip():
                continue
            calls.append(PlannedToolCall(call_id=call_id, name=name.strip(), arguments=arguments))
        return calls

    def _extract_responses_text(self, response: Any) -> str:
        output_text = self._read_attr_or_key(response, "output_text")
        if isinstance(output_text, str):
            return output_text

        output_items = self._extract_responses_output_items(response)
        collected: list[str] = []
        for item in output_items:
            item_type = self._read_attr_or_key(item, "type")
            if item_type != "message":
                continue
            content_items = self._read_attr_or_key(item, "content")
            if not isinstance(content_items, list):
                continue
            for content_item in content_items:
                content_type = self._read_attr_or_key(content_item, "type")
                if content_type != "output_text":
                    continue
                text_value = self._read_attr_or_key(content_item, "text")
                if isinstance(text_value, str):
                    collected.append(text_value)
        return "".join(collected)

    def _extract_responses_output_items(self, response: Any) -> list[Any]:
        output = self._read_attr_or_key(response, "output")
        if isinstance(output, list):
            return output
        return []

    def _read_attr_or_key(self, payload: Any, name: str) -> Any:
        value = getattr(payload, name, None)
        if value is not None:
            return value
        if isinstance(payload, dict):
            return payload.get(name)
        return None

    async def _stream_unstructured_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        temperature: float | None,
        tools: list[dict[str, Any]] | None,
        tool_choice: str | None,
        user_id: uuid.UUID | None,
        model: str,
        num_retries: int | None,
        tool_targets: dict[str, ToolTarget],
        mcp_config: MCPConfig | None,
        metadata: dict[str, Any] | None,
    ) -> AsyncGenerator[str]:
        """Stream an unstructured chat completion, optionally executing tool calls.

        Yields plain text deltas (not SSE). The caller owns transport formatting.
        """
        conversation = list(messages)
        full_text: list[str] = []
        tool_round = 0
        used_tool_names_in_turn: set[str] = set()

        try:
            while True:
                tool_round += 1
                if tool_round > _MAX_AUTONOMY_ROUNDS:
                    self._logger.warning("Stopping tool loop after %s rounds for user %s", tool_round - 1, user_id)
                    break

                # Stream from the model.
                stream = await self.complete(
                    messages=conversation,
                    temperature=temperature,
                    tools=tools,
                    tool_choice=tool_choice,
                    user_id=user_id,
                    metadata=metadata,
                    stream=True,
                    model=model,
                    num_retries=num_retries,
                    max_completion_tokens=None,
                    parallel_tool_calls=bool(tools),
                )

                chunks: list[Any] = []
                round_text: list[str] = []
                async for chunk in stream:
                    chunks.append(chunk)
                    delta = self._extract_stream_delta_content(chunk)
                    if delta:
                        full_text.append(delta)
                        round_text.append(delta)
                        yield delta

                built_message = self._rebuild_stream_message(chunks, conversation)
                tool_calls = self._extract_message_tool_calls(built_message)
                assistant_content = self._extract_message_content(built_message)

                # If we didn't get rebuilt content, fall back to what we already streamed this round.
                if not assistant_content:
                    assistant_content = "".join(round_text)

                if tool_calls:
                    normalized_tool_calls = self._normalize_chat_tool_calls(tool_calls)
                    used_tool_names_in_turn.update(call.name for call in normalized_tool_calls)
                    await self._append_tool_calls(
                        conversation,
                        assistant_content=assistant_content,
                        tool_calls=tool_calls,
                        user_id=user_id,
                        tool_targets=tool_targets,
                        mcp_config=mcp_config,
                    )
                    continue

                self._log_learning_capability_turn(
                    tool_targets=tool_targets,
                    used_tool_names=used_tool_names_in_turn,
                    conversation=conversation,
                    user_id=user_id,
                    phase="streaming",
                )
                break
        except _COMPLETION_RUNTIME_ERROR_TYPES as error:
            mapped = self._map_runtime_error(error, default_message="Completion failed")
            self._log_runtime_error(mapped, operation="Completion")
            raise mapped from error

        # Save conversation to memory (non-blocking). Keep this best-effort.
        self._schedule_memory_save(user_id, conversation, "".join(full_text))

    def _rebuild_stream_message(self, chunks: list[Any], conversation: list[dict[str, Any]]) -> Any | None:
        try:
            built = litellm.stream_chunk_builder(chunks, messages=conversation)
        except litellm.APIError:
            self._logger.debug("ai.stream.chunk_builder.failed", exc_info=True)
            return None
        return self._extract_first_choice_message(built)

    def _extract_first_choice_message(self, payload: Any) -> Any | None:
        choices = getattr(payload, "choices", None)
        if choices is None and isinstance(payload, dict):
            choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return None

        choice0 = choices[0]
        message = getattr(choice0, "message", None)
        if message is None and isinstance(choice0, dict):
            message = choice0.get("message")
        return message

    def _extract_message_tool_calls(self, message: Any) -> Any | None:
        if message is None:
            return None
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls is None and isinstance(message, dict):
            tool_calls = message.get("tool_calls")
        return tool_calls

    def _extract_message_content(self, message: Any) -> str:
        if message is None:
            return ""
        content = getattr(message, "content", None)
        if content is None and isinstance(message, dict):
            content = message.get("content")
        return content if isinstance(content, str) else ""

    def _extract_stream_delta_content(self, chunk: Any) -> str:
        """Extract the streamed text delta from a LiteLLM/OpenAI-style chunk."""
        choices = getattr(chunk, "choices", None)
        if choices is None and isinstance(chunk, dict):
            choices = chunk.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""

        choice0 = choices[0]
        delta = getattr(choice0, "delta", None)
        if delta is None and isinstance(choice0, dict):
            delta = choice0.get("delta")
        if delta is None:
            return ""

        content = getattr(delta, "content", None)
        if content is None and isinstance(delta, dict):
            content = delta.get("content")
        return content if isinstance(content, str) else ""

    def _normalize_user_id(self, user_id: str | uuid.UUID | None) -> uuid.UUID | None:
        if user_id is None:
            return None
        if isinstance(user_id, uuid.UUID):
            return user_id
        try:
            return uuid.UUID(str(user_id))
        except (ValueError, TypeError):
            self._logger.warning("Ignoring invalid user_id: %s", user_id)
            return None

    def _build_response_format(self, response_model: type[BaseModel]) -> dict[str, Any]:
        schema = response_model.model_json_schema()
        return {
            "type": "json_schema",
            "json_schema": {
                "name": response_model.__name__,
                "schema": schema,
            },
        }

    def _coerce_response_model(
        self,
        raw_response: Any,
        response_model: type[BaseModel],
    ) -> BaseModel:
        message = self._extract_first_choice_message(raw_response)
        if message is not None:
            parsed_candidate = getattr(message, "parsed", None)
            if parsed_candidate is None and isinstance(message, dict):
                parsed_candidate = message.get("parsed")
            parsed_result = self._try_convert_payload(parsed_candidate, response_model)
            if parsed_result is not None:
                return parsed_result

            content_candidate = self._extract_message_content(message)
            parsed_result = self._try_convert_payload(content_candidate, response_model)
            if parsed_result is not None:
                return parsed_result

            msg = f"Unable to coerce structured response into {response_model.__name__}"
            raise TypeError(msg)

        model_instance = self._try_convert_payload(raw_response, response_model)
        if model_instance is not None:
            return model_instance

        msg = f"Unable to coerce structured response into {response_model.__name__}"
        raise TypeError(msg)

    def _try_convert_payload(
        self,
        payload: Any,
        response_model: type[BaseModel],
    ) -> BaseModel | None:
        if payload is None:
            return None

        converted: BaseModel | None = None

        if isinstance(payload, response_model):
            converted = payload
        elif isinstance(payload, BaseModel):
            converted = self._safe_model_construct(response_model, payload.model_dump())
        elif isinstance(payload, dict):
            converted = self._safe_model_construct(response_model, payload)
        elif isinstance(payload, list):
            text_parts = [
                item["text"]
                for item in payload
                if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str)
            ]
            if text_parts:
                converted = self._try_convert_payload("".join(text_parts), response_model)
        elif isinstance(payload, str):
            content = payload.strip()
            if content:
                try:
                    decoded = json.loads(content)
                except json.JSONDecodeError:
                    decoded = None
                if isinstance(decoded, dict):
                    converted = self._safe_model_construct(response_model, decoded)

        return converted

    def _safe_model_construct(
        self,
        response_model: type[BaseModel],
        data: dict[str, Any],
    ) -> BaseModel | None:
        try:
            return response_model.model_validate(data)
        except ValidationError:
            return None

    async def _append_tool_calls(
        self,
        conversation: list[dict[str, Any]],
        *,
        assistant_content: str,
        tool_calls: list[Any],
        user_id: uuid.UUID | None,
        tool_targets: dict[str, ToolTarget],
        mcp_config: MCPConfig | None,
    ) -> None:
        conversation.append(
            {
                "role": "assistant",
                "content": assistant_content,
                "tool_calls": [self._serialize_tool_call_payload(tool_call) for tool_call in tool_calls],
            }
        )

        normalized_calls = self._normalize_chat_tool_calls(tool_calls)
        if not normalized_calls:
            return
        executed_calls = await execute_planned_tool_calls(
            calls=normalized_calls,
            tool_targets=tool_targets,
            user_id=user_id,
            mcp_config=mcp_config,
            logger=self._logger,
        )
        conversation.extend(
            {
                "role": "tool",
                "tool_call_id": executed_call.call_id,
                "name": executed_call.name,
                "content": executed_call.content,
            }
            for executed_call in executed_calls
        )

    def _serialize_tool_call_payload(self, tool_call: Any) -> dict[str, Any]:
        if hasattr(tool_call, "model_dump"):
            dumped = tool_call.model_dump()
            if isinstance(dumped, dict):
                return dumped
        if isinstance(tool_call, dict):
            return tool_call
        tool_id = self._read_attr_or_key(tool_call, "id")
        function_payload = self._read_attr_or_key(tool_call, "function")
        function_name = self._read_attr_or_key(function_payload, "name")
        function_arguments = self._read_attr_or_key(function_payload, "arguments")
        return {
            "id": tool_id,
            "type": "function",
            "function": {
                "name": function_name,
                "arguments": function_arguments,
            },
        }

    def _normalize_chat_tool_calls(self, tool_calls: list[Any]) -> list[PlannedToolCall]:
        normalized: list[PlannedToolCall] = []
        for tool_call in tool_calls:
            function_payload = self._read_attr_or_key(tool_call, "function")
            name = self._read_attr_or_key(function_payload, "name")
            arguments = self._read_attr_or_key(function_payload, "arguments")
            call_id = self._read_attr_or_key(tool_call, "id")
            if not isinstance(call_id, str) or not call_id.strip():
                continue
            if not isinstance(name, str) or not name.strip():
                continue
            normalized.append(PlannedToolCall(call_id=call_id, name=name.strip(), arguments=arguments))
        return normalized

    async def _inject_memory_into_messages(self, messages: list[dict[str, Any]], user_id: uuid.UUID) -> list[dict[str, Any]]:
        """Inject user memory context into the conversation."""
        query_text = self._build_memory_query(messages)
        if not query_text:
            return messages

        try:
            from src.ai.memory import search_memories

            memories = await search_memories(
                user_id=user_id,
                query=query_text,
                limit=6,
                agent_id=self._agent_id,
            )
        except _MEMORY_OPERATION_ERROR_TYPES as error:
            self._logger.warning("Failed to inject memory for user %s: %s", user_id, error)
            return messages

        if not memories:
            return messages

        memory_lines: list[str] = []
        for memory in memories:
            if not isinstance(memory, dict):
                continue

            candidate = memory.get("memory")
            if not isinstance(candidate, str):
                candidate = memory.get("content")
            if not isinstance(candidate, str):
                continue

            normalized = candidate.strip()
            if normalized:
                memory_lines.append(f"• {normalized}")

        if not memory_lines:
            return messages

        memory_context = MEMORY_CONTEXT_SYSTEM_PROMPT.format(memory_context="\n".join(memory_lines))
        memory_message = {"role": "system", "content": memory_context}

        if messages and messages[0].get("role") == "system":
            return [messages[0], memory_message, *messages[1:]]
        return [memory_message, *messages]

    def _build_memory_query(self, messages: list[dict[str, Any]]) -> str | None:
        """Return the most recent user utterance to drive mem0 vector search."""
        for message in reversed(messages):
            if message.get("role") != "user":
                continue
            content = message.get("content")
            if isinstance(content, str):
                normalized = content.strip()
                if normalized:
                    return normalized
            if isinstance(content, list):
                text_parts: list[str] = []
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    if part.get("type") != "text":
                        continue
                    text = part.get("text")
                    if isinstance(text, str) and text.strip():
                        text_parts.append(text.strip())
                normalized = " ".join(text_parts).strip()
                if normalized:
                    return normalized
        return None

    def _slug_tool_key(self, server_name: str, tool_name: str) -> str:
        base = f"{server_name}_{tool_name}".lower()
        return "".join(char if char.isalnum() or char == "_" else "_" for char in base)

    def _normalize_user_prompt_content(self, user_prompt: str | list[dict[str, Any]]) -> str | list[dict[str, Any]]:
        if isinstance(user_prompt, str):
            prompt_text = user_prompt.strip()
            if not prompt_text:
                msg = "User prompt must not be empty"
                raise ValueError(msg)
            return prompt_text

        if isinstance(user_prompt, list):
            text_parts = [
                part.get("text", "").strip()
                for part in user_prompt
                if isinstance(part, dict) and part.get("type") == "text"
            ]
            prompt_text = " ".join(part for part in text_parts if part)
            if not prompt_text:
                msg = "User prompt must not be empty"
                raise ValueError(msg)
            return user_prompt

        msg = "User prompt must be a string or list of content parts"
        raise TypeError(msg)

    async def generate_course_structure(
        self,
        user_prompt: str | list[dict[str, Any]],
        user_id: str | uuid.UUID | None = None,
    ) -> CourseStructure:
        """Generate a structured learning course using LiteLLM structured output (Pydantic)."""
        tracer = trace.get_tracer(__name__)
        try:
            normalized_content = self._normalize_user_prompt_content(user_prompt)
            messages = [
                {"role": "system", "content": COURSE_GENERATION_PROMPT},
                {"role": "user", "content": normalized_content},
            ]
            with tracer.start_as_current_span("llm.generation.course") as span:
                span.set_attribute("llm.generation.name", "course_generation")
                span.set_attribute("llm.model.type", "structured")
                if user_id is not None:
                    span.set_attribute("enduser.id", str(user_id))

                result = await self.get_completion(
                    messages,
                    response_model=CourseStructure,
                    user_id=user_id,
                    metadata={
                        "generation_name": "course_generation",
                        "tags": ["course", "generation"],
                    },
                )
            if not isinstance(result, CourseStructure):
                msg = "Expected CourseStructure from structured output"
                raise TypeError(msg)
            return result
        except ValueError:
            raise
        except _GENERATION_WRAPPER_ERROR_TYPES as error:
            self._logger.exception("Error generating course structure")
            msg = "Failed to generate course outline"
            raise RuntimeError(msg) from error

    async def generate_adaptive_course_structure(
        self,
        user_prompt: str | list[dict[str, Any]],
        user_id: str | uuid.UUID | None = None,
    ) -> AdaptiveCourseStructure:
        """Generate the unified adaptive course payload used by ConceptFlow."""
        tracer = trace.get_tracer(__name__)
        try:
            normalized_content = self._normalize_user_prompt_content(user_prompt)
            messages = [
                {"role": "system", "content": ADAPTIVE_COURSE_GENERATION_PROMPT},
                {"role": "user", "content": normalized_content},
            ]
            with tracer.start_as_current_span("llm.generation.adaptive_course") as span:
                span.set_attribute("llm.generation.name", "adaptive_course_generation")
                span.set_attribute("llm.model.type", "structured")
                if user_id is not None:
                    span.set_attribute("enduser.id", str(user_id))

                result = await self.get_completion(
                    messages,
                    response_model=AdaptiveCourseStructure,
                    user_id=user_id,
                    metadata={
                        "generation_name": "adaptive_course_generation",
                        "tags": ["course", "adaptive"],
                    },
                )
            if not isinstance(result, AdaptiveCourseStructure):
                msg = "Expected AdaptiveCourseStructure from structured output"
                raise TypeError(msg)
            return result
        except ValueError:
            raise
        except _GENERATION_WRAPPER_ERROR_TYPES as error:
            self._logger.exception("Error generating adaptive course structure")
            msg = "Failed to generate adaptive course structure"
            raise RuntimeError(msg) from error

    async def generate_self_assessment_questions(
        self,
        *,
        topic: str,
        level: str | None = None,
        user_id: str | uuid.UUID | None = None,
    ) -> SelfAssessmentQuiz:
        """Generate optional self-assessment questions for a course topic."""
        tracer = trace.get_tracer(__name__)
        normalized_topic = topic.strip()
        if not normalized_topic:
            msg = "Topic must not be empty"
            raise ValueError(msg)

        level_text = level.strip() if level else "unspecified"

        try:
            settings = get_settings()
            messages = [
                {
                    "role": "system",
                    "content": SELF_ASSESSMENT_QUESTIONS_PROMPT.format(
                        topic=normalized_topic,
                        level=level_text,
                    ),
                },
                {
                    "role": "user",
                    "content": "Draft optional multiple-choice self-assessment questions to personalize the course.",
                },
            ]

            with tracer.start_as_current_span("llm.generation.self_assessment") as span:
                span.set_attribute("llm.generation.name", "self_assessment_generation")
                span.set_attribute("llm.topic", normalized_topic)
                span.set_attribute("llm.level", level_text)
                if user_id is not None:
                    span.set_attribute("enduser.id", str(user_id))

                result = await self.get_completion(
                    messages,
                    response_model=SelfAssessmentQuiz,
                    user_id=user_id,
                    model=settings.FAST_LLM_MODEL.strip() or None,
                    metadata={
                        "generation_name": "self_assessment_generation",
                        "tags": ["self_assessment", "generation"],
                        "topic": normalized_topic,
                        "level": level_text,
                    },
                )

            if not isinstance(result, SelfAssessmentQuiz):
                msg = "Expected SelfAssessmentQuiz from structured output"
                raise TypeError(msg)

            return result

        except _GENERATION_WRAPPER_ERROR_TYPES as error:
            self._logger.exception("Error generating self-assessment questions")
            msg = "Failed to generate self-assessment questions"
            raise RuntimeError(msg) from error

    async def generate_lesson_content(
        self,
        lesson_context: str,
        user_id: str | uuid.UUID | None = None,
    ) -> LessonContent:
        """Generate a lesson body from a prepared LESSON_CONTEXT string."""
        context_text = lesson_context.strip()
        if not context_text:
            msg = "Lesson context must not be empty"
            raise ValueError(msg)

        normalized_user_id = self._normalize_user_id(user_id)

        messages = [
            {"role": "system", "content": LESSON_GENERATION_PROMPT},
            {"role": "user", "content": context_text},
        ]

        try:
            response_content = await self.get_completion(
                messages,
                user_id=normalized_user_id,
            )

            content = response_content if isinstance(response_content, str) else str(response_content or "")
            return LessonContent(body=content.strip())
        except _GENERATION_WRAPPER_ERROR_TYPES as error:
            self._logger.exception("Error generating lesson content")
            msg = "Failed to generate lesson content"
            raise RuntimeError(msg) from error

    async def generate_execution_plan(
        self,
        *,
        language: str,
        source_code: str,
        stderr: str | None = None,
        stdin: str | None = None,
        sandbox_state: dict[str, Any] | None = None,
        user_id: str | uuid.UUID | None = None,
        workspace_entry: str | None = None,
        workspace_root: str | None = None,
        workspace_files: list[str] | None = None,
        workspace_id: str | None = None,
        sandbox_context: SandboxToolContext | None = None,
    ) -> ExecutionPlan:
        """Create a sandbox execution plan using Instructor-bound JSON output."""
        payload: dict[str, Any] = {
            "language": language,
            "source_code": source_code[:6000],
            "source_code_truncated": len(source_code) > 6000,
            "stderr": (stderr or "")[:4000],
            "stdin": (stdin or "")[:2000],
            "sandbox_state": sandbox_state or {},
        }
        if workspace_entry:
            payload["workspace_entry"] = workspace_entry
        if workspace_root:
            payload["workspace_root"] = workspace_root
        if workspace_files:
            payload["workspace_files"] = workspace_files
        if workspace_id:
            payload["workspace_id"] = workspace_id

        messages = [
            {"role": "system", "content": E2B_EXECUTION_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
        ]

        try:
            settings = get_settings()
            plan = await self.get_completion(
                messages,
                response_model=ExecutionPlan,
                user_id=user_id,
                model=settings.FAST_LLM_MODEL.strip() or None,
                sandbox_context=sandbox_context,
                max_completion_tokens=settings.CODE_EXECUTION_MAX_COMPLETION_TOKENS,
            )

            if not isinstance(plan, ExecutionPlan):
                msg = "Expected ExecutionPlan from structured output"
                raise TypeError(msg)

            return plan

        except _GENERATION_WRAPPER_ERROR_TYPES as exc:
            self._logger.exception("Failed to generate execution plan")
            msg = "Execution planning failed"
            raise RuntimeError(msg) from exc

    async def generate_grading_coach_feedback(
        self,
        *,
        payload: dict[str, Any],
        response_model: type[T],
        user_id: str | uuid.UUID | None = None,
        model: str | None = None,
    ) -> T:
        """Generate grading coach feedback with a strict structured contract."""
        messages = [
            {"role": "system", "content": GRADING_COACH_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
        ]

        result = await self.get_completion(
            messages,
            response_model=response_model,
            user_id=user_id,
            model=model,
        )
        if not isinstance(result, response_model):
            msg = f"Expected {response_model.__name__} from grading coach structured output"
            raise TypeError(msg)
        return result

    async def generate_practice_question_batch(
        self,
        *,
        concept: str,
        concept_description: str | None,
        history: str,
        learner_context: str,
        difficulty_guidance: str,
        count: int,
        response_model: type[T],
        user_id: str | uuid.UUID | None = None,
        model: str | None = None,
    ) -> T:
        """Generate a structured batch of practice questions."""
        prompt = PRACTICE_GENERATION_PROMPT.format(
            count=count,
            concept=concept,
            concept_description=concept_description or "",
            learner_context=learner_context,
            difficulty_guidance=difficulty_guidance,
            history=history,
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Generate the questions now."},
        ]

        result = await self.get_completion(
            messages,
            response_model=response_model,
            user_id=user_id,
            model=model,
        )
        if not isinstance(result, response_model):
            msg = f"Expected {response_model.__name__} from practice generation structured output"
            raise TypeError(msg)
        return result

    async def grade_adaptive_practice_answer(
        self,
        *,
        payload: dict[str, Any],
        response_model: type[T],
        user_id: str | uuid.UUID | None = None,
        model: str | None = None,
    ) -> T:
        """Grade an adaptive practice answer via the shared structured completion path."""
        messages = [
            {"role": "system", "content": ADAPTIVE_PRACTICE_GRADING_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
        ]

        result = await self.get_completion(
            messages,
            response_model=response_model,
            user_id=user_id,
            model=model,
        )
        if not isinstance(result, response_model):
            msg = f"Expected {response_model.__name__} from adaptive practice grading structured output"
            raise TypeError(msg)
        return result

    async def predict_practice_correctness_batch(
        self,
        *,
        concept: str,
        mastery: float,
        recent_correct: int,
        recent_total: int,
        learning_speed: float,
        retention_rate: float,
        success_rate: float,
        struggling_concepts: list[str],
        review_status: str,
        questions: list[str],
        predictions_example: str,
        response_model: type[T],
        user_id: str | uuid.UUID | None = None,
        model: str | None = None,
    ) -> T:
        """Predict p(correct) values for a batch of candidate practice questions."""
        questions_block = "\n".join(f"{index + 1}. {question}" for index, question in enumerate(questions))
        struggling_concepts_block = ", ".join(struggling_concepts) if struggling_concepts else "none"
        prompt = PRACTICE_PREDICTION_PROMPT.format(
            concept=concept,
            mastery=mastery,
            recent_correct=recent_correct,
            recent_total=recent_total,
            learning_speed=learning_speed,
            retention_rate=retention_rate,
            success_rate=success_rate,
            struggling_concepts=struggling_concepts_block,
            review_status=review_status,
            questions=questions_block,
            predictions_example=predictions_example,
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Return predicted probabilities."},
        ]

        result = await self.get_completion(
            messages,
            response_model=response_model,
            user_id=user_id,
            model=model,
        )
        if not isinstance(result, response_model):
            msg = f"Expected {response_model.__name__} from practice prediction structured output"
            raise TypeError(msg)
        return result

    async def _save_conversation_to_memory(
        self, user_id: uuid.UUID | None, messages: list[dict[str, Any]], response: Any
    ) -> None:
        """Save conversation to memory using mem0.

        This runs async in background - never blocks the user response.
        mem0 handles all the intelligent extraction, deduplication, and preference detection.
        """
        if user_id is None:
            return

        try:
            from src.ai.memory import add_memory
        except ImportError as error:
            self._logger.warning("Failed to save conversation to memory: %s", error)
            return

        user_message = self._build_memory_query(messages) or ""
        ai_response = self._extract_memory_response_text(response)

        memory_messages: list[dict[str, Any]] = []
        if user_message:
            memory_messages.append({"role": "user", "content": user_message})
        if ai_response:
            memory_messages.append({"role": "assistant", "content": ai_response})

        if not memory_messages:
            return

        try:
            # Let mem0 handle everything - extraction, deduplication, relevance filtering
            await add_memory(
                user_id=user_id,
                messages=memory_messages,
                agent_id=self._agent_id,
            )
        except _MEMORY_OPERATION_ERROR_TYPES as error:
            # Never fail the main request due to memory issues
            self._logger.warning("Failed to save conversation to memory: %s", error)

    def _extract_memory_response_text(self, response: Any) -> str:
        if isinstance(response, str):
            return response[:1000]
        if hasattr(response, "choices"):
            message = self._extract_first_choice_message(response)
            content = self._extract_message_content(message)
            return content[:1000]
        if hasattr(response, "model_dump"):
            return str(response.model_dump())[:1000]
        return str(response)[:1000]
