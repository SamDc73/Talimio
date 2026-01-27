import asyncio
import json
import logging
import os
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID


if TYPE_CHECKING:
    from src.auth.context import AuthContext

from collections import Counter

import litellm
from pydantic import BaseModel, ValidationError


T = TypeVar("T", bound=BaseModel)

from src.ai import AGENT_ID_DEFAULT
from src.ai.mcp.service import get_user_mcp_config
from src.ai.mcp.tooling import (
    MCPToolBinding,
    build_tool_instruction,
    execute_user_tool_call,
    load_user_tool_bindings,
    parse_tool_arguments,
)
from src.ai.models import (
    AdaptiveCourseStructure,
    CourseStructure,
    ExecutionPlan,
    LessonContent,
    SelfAssessmentQuiz,
)
from src.ai.prompts import (
    ADAPTIVE_COURSE_GENERATION_PROMPT,
    COURSE_GENERATION_PROMPT,
    E2B_EXECUTION_SYSTEM_PROMPT,
    LESSON_GENERATION_PROMPT,
    MDX_ERROR_FIX_PROMPT,
    MEMORY_CONTEXT_SYSTEM_PROMPT,
    SELF_ASSESSMENT_QUESTIONS_PROMPT,
)
from src.config.settings import get_settings
from src.database.session import async_session_maker


class LLMClient:
    """Manages LLM completion requests with memory integration and RAG support."""

    def __init__(self, rag_service: Any | None = None, agent_id: str = AGENT_ID_DEFAULT) -> None:
        """Initialize LLMClient.

        Args:
            rag_service: Optional RAGService instance for dependency injection.
                        If not provided, RAG functionality will be skipped or create a new instance.
            agent_id: Logical identifier for the caller so memories can be scoped per module.
        """
        self._logger = logging.getLogger(__name__)
        self._rag_service = rag_service
        self._agent_id = agent_id
        self._tool_maps: dict[UUID, dict[str, tuple[str, str]]] = {}
        self._tool_filters = self._parse_tool_filters()
        self._background_tasks: set[asyncio.Task[Any]] = set()

    def _parse_tool_filters(self) -> tuple[set[str] | None, set[str]]:
        allowed_env = os.getenv("AI_ENABLED_TOOLS")
        allowed = {token.strip().lower() for token in allowed_env.split(",") if token.strip()} if allowed_env else None
        blocked_env = os.getenv("AI_DISABLED_TOOLS")
        blocked = {token.strip().lower() for token in blocked_env.split(",") if token.strip()} if blocked_env else set()
        return allowed, blocked

    async def complete(
        self,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
        user_id: str | UUID | None = None,
        response_format: Any | None = None,
        stream: bool = False,
        model: str | None = None,
    ) -> Any:
        """Low-level completion method using LiteLLM directly."""
        try:
            # Get model from settings
            settings = get_settings()
            request_model = model or settings.primary_llm_model

            kwargs = {
                "model": request_model,
                "messages": messages,
                "timeout": settings.ai_request_timeout,
            }

            if temperature is not None:
                kwargs["temperature"] = temperature
            if tools:
                kwargs["tools"] = tools
            if tool_choice:
                kwargs["tool_choice"] = tool_choice
            if response_format is not None:
                kwargs["response_format"] = response_format
            if user_id:
                # Pass user identifier for provider-side tracking / rate limits when supported
                # Safe with litellm.drop_params=True across providers
                # Convert UUID to string for JSON serialization
                kwargs["user"] = str(user_id)
            if stream:
                kwargs["stream"] = stream

            return await asyncio.wait_for(litellm.acompletion(**kwargs), timeout=settings.ai_request_timeout)

        except Exception as e:
            self._logger.exception("Error in model completion")
            msg = f"Model completion failed: {e}"
            raise RuntimeError(msg) from e

    async def get_completion(
        self,
        messages: list[dict[str, Any]],
        response_model: type[BaseModel] | None = None,
        temperature: float | None = None,
        tools: list[dict[str, Any]] | list[MCPToolBinding] | None = None,
        tool_choice: str | None = None,
        user_id: str | UUID | None = None,
        model: str | None = None,
    ) -> Any:
        """Get completion with optional memory integration and structured output."""
        try:
            normalized_user_id = self._normalize_user_id(user_id)
            settings = get_settings()
            request_model = model or settings.primary_llm_model
            if normalized_user_id:
                messages = await self._inject_memory_into_messages(messages, normalized_user_id)

            # Handle structured output via LiteLLM json schema with Instructor fallback
            tool_sources: list[dict[str, Any]] | list[MCPToolBinding] | None = tools
            if tool_sources is None and normalized_user_id is not None:
                tool_sources = await self._load_user_tool_bindings(normalized_user_id)
            tool_schemas: list[dict[str, Any]] | None = self._prepare_tool_schemas(tool_sources, normalized_user_id)
            effective_tool_choice = tool_choice or ("auto" if tool_schemas else None)

            if response_model:

                def _finalize(structured: BaseModel) -> BaseModel:
                    if normalized_user_id:
                        task = asyncio.create_task(
                            self._save_conversation_to_memory(normalized_user_id, messages, structured)
                        )
                        self._background_tasks.add(task)
                        task.add_done_callback(self._background_tasks.discard)
                    return structured

                schema_instance = await self._complete_with_litellm_schema(
                    messages=messages,
                    schema_model=response_model,
                    temperature=temperature,
                    user_id=normalized_user_id,
                    model=request_model,
                    tools=tool_schemas,
                    tool_choice=effective_tool_choice,
                )

                return _finalize(schema_instance)

            # Handle function calling
            if tool_schemas:
                response = await self.complete(
                    messages=messages,
                    temperature=temperature,
                    tools=tool_schemas,
                    tool_choice=effective_tool_choice,
                    user_id=normalized_user_id,
                )

                # Process function calls
                if response.choices[0].message.tool_calls:
                    return await self._handle_function_calling(
                        response, messages, temperature, normalized_user_id
                    )

                return response.choices[0].message.content

            # Regular completion
            response = await self.complete(
                messages=messages,
                temperature=temperature,
                user_id=normalized_user_id,
                model=model,
            )

            content = response.choices[0].message.content

            # Save conversation to memory (non-blocking)
            if normalized_user_id and response:
                task = asyncio.create_task(
                    self._save_conversation_to_memory(normalized_user_id, messages, content)
                )
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)


            return content

        except Exception as e:
            self._logger.exception("Error in get_completion")
            msg = f"Completion failed: {e}"
            raise RuntimeError(msg) from e

    def _normalize_user_id(self, user_id: str | UUID | None) -> UUID | None:
        if user_id is None:
            return None
        if isinstance(user_id, UUID):
            return user_id
        try:
            return UUID(str(user_id))
        except (ValueError, TypeError):
            self._logger.warning("Ignoring invalid user_id: %s", user_id)
            return None

    async def _complete_with_litellm_schema(
        self,
        *,
        messages: list[dict[str, Any]],
        schema_model: type[BaseModel],
        temperature: float | None,
        user_id: UUID | None,
        model: str,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
    ) -> BaseModel:
        last_error: Exception | None = None
        attempt = 0
        conversation = list(messages)
        while attempt < 2:
            response = await self.complete(
                messages=conversation,
                temperature=temperature,
                user_id=user_id,
                response_format=self._build_response_format(schema_model),
                model=model,
                tools=tools,
                tool_choice=tool_choice,
            )
            assistant_message = response.choices[0].message
            tool_calls = getattr(assistant_message, "tool_calls", None)
            if tool_calls:
                await self._append_tool_calls(
                    conversation,
                    assistant_content=assistant_message.content or "",
                    tool_calls=tool_calls,
                    user_id=user_id,
                )
                if user_id is None:
                    self._logger.warning("Structured output invoked MCP tools without a user context")
                    break
                continue
            try:
                return self._coerce_response_model(response, schema_model)
            except Exception as parse_error:
                last_error = parse_error
                attempt += 1
                self._logger.warning(
                    "Structured response validation failed on attempt %s: %s",
                    attempt,
                    parse_error,
                )
                if attempt < 2:
                    conversation.append(
                        {
                            "role": "user",
                            "content": (
                                "Your previous response did not match the required JSON schema. "
                                "Reply again with ONLY valid JSON that matches the schema exactly "
                                "(no markdown, no commentary, no extra keys)."
                            ),
                        }
                    )
        if last_error is None:
            msg = "Structured response validation failed"
            raise RuntimeError(msg)
        raise last_error

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
        choices = getattr(raw_response, "choices", None)
        if choices:
            first_choice = choices[0]
            message = getattr(first_choice, "message", None)
            if message is not None:
                parsed_candidate = getattr(message, "parsed", None)
                parsed_result = self._try_convert_payload(parsed_candidate, response_model)
                if parsed_result is not None:
                    return parsed_result
                content_candidate = getattr(message, "content", None)
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
        user_id: UUID | None,
    ) -> None:
        conversation.append(
            {
                "role": "assistant",
                "content": assistant_content,
                "tool_calls": [tc.model_dump() for tc in tool_calls],
            }
        )

        if user_id is None:
            return

        executed = await self._execute_tool_calls(tool_calls, user_id)
        for tool_call, result_content in executed:
            conversation.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_content,
                }
            )

    async def _inject_memory_into_messages(self, messages: list[dict[str, Any]], user_id: UUID) -> list[dict[str, Any]]:
        """Inject user memory context into the conversation."""
        try:
            # Get user memory
            from src.ai.memory import search_memories

            query_text = self._build_memory_query(messages)
            if not query_text:
                return messages

            memories = await search_memories(
                user_id=user_id,
                query=query_text,
                limit=6,
                agent_id=self._agent_id,
            )

            if not memories:
                return messages

            # Format memories as context
            user_memory = "\n".join(
                [f"• {m.get('memory', m.get('content', ''))}" for m in memories if m.get("memory") or m.get("content")]
            )

            if not user_memory:
                return messages

            # Create memory context message
            memory_context = MEMORY_CONTEXT_SYSTEM_PROMPT.format(memory_context=user_memory)
            memory_message = {"role": "system", "content": memory_context}

            # Insert after the first system message (if exists) or at the beginning
            if messages and messages[0].get("role") == "system":
                return [messages[0], memory_message, *messages[1:]]
            return [memory_message, *messages]

        except Exception as e:
            self._logger.warning(f"Failed to inject memory for user {user_id}: {e}")
            return messages

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
        return None

    async def _handle_function_calling(
        self,
        response: Any,
        messages: list[dict[str, Any]],
        temperature: float | None,
        user_id: UUID | None,
    ) -> str:
        """Handle function calling responses."""
        assistant_message = response.choices[0].message
        await self._append_tool_calls(
            messages,
            assistant_content=assistant_message.content or "",
            tool_calls=assistant_message.tool_calls,
            user_id=user_id,
        )

        if user_id is None:
            self._logger.warning("Model attempted to call MCP tools without a user context")
            return assistant_message.content or ""

        final_response = await self.complete(
            messages=messages,
            temperature=temperature,
            user_id=user_id,
        )

        return final_response.choices[0].message.content

    def _prepare_tool_schemas(
        self,
        tools: list[dict[str, Any]] | list[MCPToolBinding] | None,
        user_id: UUID | None,
    ) -> list[dict[str, Any]] | None:
        if not tools:
            if user_id is not None:
                self._tool_maps.pop(user_id, None)
            return None
        first = tools[0]
        if isinstance(first, MCPToolBinding):
            if user_id is None:
                self._logger.debug("MCP tools provided but user_id is missing; skipping tool wiring")
                return None
            bindings = cast("list[MCPToolBinding]", tools)
            filtered = self._filter_tool_bindings(bindings)
            if not filtered:
                self._tool_maps.pop(user_id, None)
                return None
            return self._assign_tool_schemas(user_id, filtered)
        schema_list = cast("list[dict[str, Any]]", tools)
        return self._filter_schema_list(schema_list)

    def _filter_schema_list(self, schemas: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        allowed, blocked = self._get_tool_filters()
        filtered: list[dict[str, Any]] = []
        for schema in schemas:
            if not isinstance(schema, dict):
                continue
            function_block = schema.get("function") or {}
            name = str(function_block.get("name", "")).strip()
            if not name:
                continue
            key = name.lower()
            if allowed is not None and key not in allowed:
                continue
            if key in blocked:
                continue
            filtered.append(schema)
        return filtered or None

    def _assign_tool_schemas(self, user_id: UUID, bindings: list[MCPToolBinding]) -> list[dict[str, Any]]:
        schemas: list[dict[str, Any]] = []
        mapping: dict[str, tuple[str, str]] = {}
        counts: Counter[str] = Counter()
        for binding in bindings:
            base = self._slug_tool_key(binding.server_name, binding.tool_name)
            counts[base] += 1
            encoded = base if counts[base] == 1 else f"{base}_{counts[base]}"
            binding.encoded_name = encoded
            mapping[encoded] = (binding.server_name, binding.tool_name)
            schemas.append(binding.to_tool_schema())
        self._tool_maps[user_id] = mapping
        return schemas

    def _filter_tool_bindings(
        self,
        bindings: list[MCPToolBinding],
    ) -> list[MCPToolBinding]:
        allowed, blocked = self._get_tool_filters()
        filtered: list[MCPToolBinding] = []
        for binding in bindings:
            key = binding.tool_name.lower()
            if allowed is not None and key not in allowed:
                continue
            if key in blocked:
                continue
            filtered.append(binding)
        return filtered

    def _slug_tool_key(self, server_name: str, tool_name: str) -> str:
        base = f"{server_name}_{tool_name}".lower()
        return "".join(char if char.isalnum() or char == "_" else "_" for char in base)

    def _get_tool_filters(self) -> tuple[set[str] | None, set[str]]:
        return self._tool_filters

    async def _load_user_tool_bindings(self, user_id: UUID) -> list[MCPToolBinding]:
        async with async_session_maker() as session:
            return await load_user_tool_bindings(session, user_id)

    async def _execute_tool_calls(
        self,
        tool_calls: list[Any],
        user_id: UUID,
    ) -> list[tuple[Any, str]]:
        formatted: list[tuple[Any, str] | None] = []
        pending: list[tuple[int, Any, dict[str, Any], tuple[str, str]]] = []
        for idx, tool_call in enumerate(tool_calls):
            target = self._resolve_tool_target(user_id, tool_call.function.name)
            if target is None:
                warning = f"Error: Tool '{tool_call.function.name}' is not available"
                formatted.append((tool_call, warning))
                continue
            try:
                args_dict = parse_tool_arguments(tool_call.function.arguments)
            except ValueError as exc:
                formatted.append((tool_call, f"Error: {exc!s}"))
                continue
            formatted.append(None)
            pending.append((idx, tool_call, args_dict, target))
            self._logger.info(
                "Queued MCP tool call",
                extra={
                    "mcp_server": target[0],
                    "mcp_tool": target[1],
                    "encoded_tool": tool_call.function.name,
                    "user_id": str(user_id),
                    "tool_call_id": getattr(tool_call, "id", None),
                },
            )
        if pending:
            # Load config once, then run all tool calls concurrently without DB sessions
            async with async_session_maker() as session:
                config = await get_user_mcp_config(session, user_id)

            tasks = [
                execute_user_tool_call(
                    user_id=user_id,
                    server_name=target[0],
                    tool_name=target[1],
                    encoded_name=tool_call.function.name,
                    arguments=args_dict,
                    config=config,
                )
                for (_idx, tool_call, args_dict, target) in pending
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for (idx, tool_call, _args_dict, target), result in zip(pending, results, strict=False):
                if isinstance(result, Exception):
                    content = f"Error: {result!s}"
                    self._logger.error(
                        "MCP tool %s failed: %s",
                        tool_call.function.name,
                        result,
                        extra={
                            "mcp_server": target[0],
                            "mcp_tool": target[1],
                            "encoded_tool": tool_call.function.name,
                            "user_id": str(user_id),
                            "tool_call_id": getattr(tool_call, "id", None),
                        },
                    )
                else:
                    content = self._format_tool_result(result)
                    self._logger.info(
                        "MCP tool %s succeeded",
                        tool_call.function.name,
                        extra={
                            "mcp_server": target[0],
                            "mcp_tool": target[1],
                            "encoded_tool": tool_call.function.name,
                            "user_id": str(user_id),
                            "tool_call_id": getattr(tool_call, "id", None),
                        },
                    )
                formatted[idx] = (tool_call, content)
        return [entry for entry in formatted if entry is not None]

    def _resolve_tool_target(self, user_id: UUID, encoded_name: str) -> tuple[str, str] | None:
        mapping = self._tool_maps.get(user_id)
        if not mapping:
            return None
        return mapping.get(encoded_name)

    def _format_tool_result(self, result: Any) -> str:
        if isinstance(result, (dict, list)):
            try:
                return json.dumps(result, default=str)
            except Exception:
                return str(result)
        return str(result)

    def _build_tooling_instruction(self, bindings: list[MCPToolBinding]) -> str | None:
        return build_tool_instruction(bindings)

    async def _apply_user_tooling(
        self,
        messages: list[dict[str, Any]],
        *,
        user_id: UUID | None,
    ) -> tuple[list[dict[str, Any]], list[MCPToolBinding]]:
        tool_bindings: list[MCPToolBinding] = []
        if user_id is not None:
            tool_bindings = await self._load_user_tool_bindings(user_id)
        tool_instruction = self._build_tooling_instruction(tool_bindings)
        if tool_instruction:
            messages = [messages[0], {"role": "system", "content": tool_instruction}, *messages[1:]]
        return messages, tool_bindings

    async def _get_rag_context(
        self,
        course_id: str | None,
        title: str,
        description: str,
        auth: "AuthContext | None" = None,
    ) -> str:
        """Get RAG context for lesson generation.

        Requires an `AuthContext` to access the RAG service. If `auth` is not provided
        or `course_id` is missing, this returns an empty string and skips RAG.

        This removes the previous direct DB/session fallback to keep concerns separated and
        align with the centralized auth strategy.
        """
        if not course_id:
            return ""

        try:
            # Use injected RAG service if available, otherwise create a new one for backward compatibility
            if self._rag_service is not None:
                rag_service = self._rag_service
            else:
                from src.ai.rag.service import RAGService

                rag_service = RAGService()

            if not auth:
                return ""

            # Create search query from title and description
            search_query = f"{title} {description}"
            search_results = await rag_service.search_documents(
                auth=auth, course_id=UUID(course_id), query=search_query, top_k=5
            )

            if not search_results:
                return ""

            # Build context
            context_parts = ["## Course Context\n"]
            for i, result in enumerate(search_results[:5], 1):
                context_parts.append(f"### Context {i}\n{result.content}\n")

            return "\n".join(context_parts)

        except Exception as e:
            self._logger.warning(f"Failed to get RAG context for course {course_id}: {e}")
            return ""

    async def _generate_structure_payload(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        user_id: str | UUID | None,
    ) -> T:
        prompt_text = user_prompt.strip()
        if not prompt_text:
            msg = "User prompt must not be empty"
            raise ValueError(msg)

        normalized_user_id = self._normalize_user_id(user_id)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_text},
        ]

        messages, tool_bindings = await self._apply_user_tooling(messages, user_id=normalized_user_id)

        result = await self.get_completion(
            messages,
            response_model=response_model,
            user_id=normalized_user_id,
            tools=tool_bindings or None,
            tool_choice="auto" if tool_bindings else None,
        )

        if not isinstance(result, response_model):
            msg = f"Expected {response_model.__name__} from structured output"
            raise TypeError(msg)

        return result

    async def generate_course_structure(
        self,
        user_prompt: str,
        user_id: str | UUID | None = None,
    ) -> CourseStructure:
        """Generate a structured learning course using LiteLLM structured output (Pydantic)."""
        try:
            return await self._generate_structure_payload(
                system_prompt=COURSE_GENERATION_PROMPT,
                user_prompt=user_prompt,
                response_model=CourseStructure,
                user_id=user_id,
            )
        except ValueError:
            raise
        except Exception as e:
            self._logger.exception("Error generating course structure")
            msg = "Failed to generate course outline"
            raise RuntimeError(msg) from e

    async def generate_adaptive_course_structure(
        self,
        user_prompt: str,
        user_id: str | UUID | None = None,
    ) -> AdaptiveCourseStructure:
        """Generate the unified adaptive course payload used by ConceptFlow."""
        try:
            return await self._generate_structure_payload(
                system_prompt=ADAPTIVE_COURSE_GENERATION_PROMPT,
                user_prompt=user_prompt,
                response_model=AdaptiveCourseStructure,
                user_id=user_id,
            )
        except ValueError:
            raise
        except Exception as e:
            self._logger.exception("Error generating adaptive course structure")
            msg = "Failed to generate adaptive course structure"
            raise RuntimeError(msg) from e

    async def generate_self_assessment_questions(
        self,
        *,
        topic: str,
        level: str | None = None,
        user_id: str | UUID | None = None,
    ) -> SelfAssessmentQuiz:
        """Generate optional self-assessment questions for a course topic."""
        normalized_topic = topic.strip()
        if not normalized_topic:
            msg = "Topic must not be empty"
            raise ValueError(msg)

        level_text = level.strip() if level else "unspecified"

        try:
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

            result = await self.get_completion(
                messages,
                response_model=SelfAssessmentQuiz,
                user_id=user_id,
            )

            if not isinstance(result, SelfAssessmentQuiz):
                msg = "Expected SelfAssessmentQuiz from structured output"
                raise TypeError(msg)

            return result

        except Exception as error:
            self._logger.exception("Error generating self-assessment questions")
            msg = "Failed to generate self-assessment questions"
            raise RuntimeError(msg) from error

    async def create_lesson(self, node_meta: dict[str, Any], auth: "AuthContext | None" = None) -> LessonContent:
        """Generate lesson content.

        Args:
            node_meta: Node metadata (title, description, course_id, user_id)
            auth: AuthContext for RAG access

        Returns
        -------
            LessonContent
        """
        try:
            title = node_meta.get("title", "Untitled")

            # Build context (course info + RAG)
            metadata = {
                "node_title": title,
                "node_description": node_meta.get("description", ""),
                "course_id": node_meta.get("course_id"),
                "user_id": node_meta.get("user_id"),
                "course_title": node_meta.get("course_title", ""),
                "original_user_prompt": node_meta.get("original_user_prompt", ""),
            }

            # Build context string
            context_parts = []
            if metadata["course_title"]:
                context_parts.append(f"Course: {metadata['course_title']}")
            if metadata["node_description"]:
                context_parts.append(f"Lesson Topic: {metadata['node_description']}")

            content_info = "## Course Information\n" + "\n".join(context_parts) + "\n\n" if context_parts else ""

            rag_context = await self._get_rag_context(
                metadata.get("course_id"),
                metadata.get("node_title") or "",
                metadata.get("node_description") or "",
                auth,
            )

            # Inject target concept context for adaptive mode (single-concept lessons)
            target = node_meta.get("target_concept") or {}
            target_section = ""
            if isinstance(target, dict) and (target.get("name") or target.get("description")):
                t_name = str(target.get("name", "")).strip()
                t_desc = str(target.get("description", "")).strip()
                t_mastery = target.get("mastery")
                lines = [
                    "## Target Concept",
                    f"Name: {t_name}" if t_name else None,
                    f"Description: {t_desc}" if t_desc else None,
                ]
                if isinstance(t_mastery, (int, float)):
                    lines.append(f"Current mastery: {float(t_mastery):.2f}")
                target_section = "\n".join([ln for ln in lines if ln]) + "\n\n"

            # Prepare prompt
            combined_content = (content_info + target_section + rag_context).strip()
            if not combined_content:
                combined_content = f"Lesson Title: {title}\nLesson Topic: {metadata['node_description'] or title}"

            system_prompt = LESSON_GENERATION_PROMPT.replace("{content}", combined_content)
            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f'Write the complete lesson titled "{title}" in Markdown,'
                        " following every instruction in the system prompt."
                    ),
                },
            ]

            # Generate lesson content
            response_content = await self.get_completion(
                messages,
                user_id=metadata.get("user_id"),
            )

            # Get content from response (litellm or tool-assisted output)
            content = response_content if isinstance(response_content, str) else str(response_content or "")

            # Validate and fix MDX - keep trying until valid (max 3 attempts)
            from src.courses.services.mdx_service import mdx_service

            max_fix_attempts = 3
            for fix_attempt in range(max_fix_attempts):
                is_valid, error_msg = mdx_service.validate_mdx(content)

                if is_valid:
                    break  # Content is valid, we're done

                # Ask AI to fix the broken MDX
                fix_messages = [
                    {"role": "assistant", "content": content},
                    {"role": "user", "content": f"MDX validation error: {error_msg}\n\n{MDX_ERROR_FIX_PROMPT}"},
                ]

                try:
                    fix_response = await self.get_completion(
                        fix_messages,
                        user_id=metadata.get("user_id"),
                    )
                    content = fix_response if isinstance(fix_response, str) else str(fix_response or "")
                except Exception as fix_error:
                    if fix_attempt == max_fix_attempts - 1:
                        # Last attempt failed, raise error
                        msg = f"Could not fix MDX after {max_fix_attempts} attempts. Last error: {error_msg[:200] if error_msg else 'Unknown error'}"
                        raise RuntimeError(msg) from fix_error

            # Final validation check
            is_valid, error_msg = mdx_service.validate_mdx(content)
            if not is_valid:
                # ALL attempts to fix failed - DO NOT save broken MDX
                msg = f"MDX still invalid after {max_fix_attempts} fix attempts: {error_msg[:200] if error_msg else 'Unknown error'}"
                raise ValueError(msg)

            return LessonContent(body=content.strip())
        except Exception as e:
            self._logger.exception("Error generating lesson content")
            msg = "Failed to generate lesson content"
            raise RuntimeError(msg) from e

    async def generate_execution_plan(
        self,
        *,
        language: str,
        source_code: str,
        stderr: str | None = None,
        stdin: str | None = None,
        sandbox_state: dict[str, Any] | None = None,
        user_id: str | UUID | None = None,
        workspace_entry: str | None = None,
        workspace_root: str | None = None,
        workspace_files: list[str] | None = None,
        workspace_id: str | None = None,
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
            plan = await self.get_completion(
                messages,
                response_model=ExecutionPlan,
                user_id=user_id,
            )

            if not isinstance(plan, ExecutionPlan):
                msg = "Expected ExecutionPlan from structured output"
                raise TypeError(msg)

            return plan

        except Exception as exc:
            self._logger.exception("Failed to generate execution plan")
            msg = "Execution planning failed"
            raise RuntimeError(msg) from exc

    async def _save_conversation_to_memory(
        self, user_id: UUID | None, messages: list[dict[str, Any]], response: Any
    ) -> None:
        """Save conversation to memory using mem0.

        This runs async in background - never blocks the user response.
        mem0 handles all the intelligent extraction, deduplication, and preference detection.
        """
        try:
            if user_id is None:
                return

            from src.ai.memory import add_memory

            # Extract the user's last message
            user_message = messages[-1].get("content", "") if messages else ""

            # Handle different response types
            if isinstance(response, str):
                ai_response = response[:1000]  # Limit to first 1000 chars
            elif hasattr(response, "choices"):
                # Raw completion response (LiteLLM / OpenAI-style)
                ai_response = response.choices[0].message.content[:1000] if response.choices else ""
            elif hasattr(response, "model_dump"):
                # Pydantic model (structured output)
                ai_response = str(response.model_dump())[:1000]
            else:
                ai_response = str(response)[:1000]

            # Combine into conversation format
            conversation = f"User: {user_message}\nAssistant: {ai_response}"

            metadata = {
                "agent_id": self._agent_id,
            }

            # Let mem0 handle everything - extraction, deduplication, relevance filtering
            await add_memory(
                user_id=user_id,
                content=conversation,
                agent_id=self._agent_id,
                metadata=metadata,
            )

        except Exception as e:
            # Never fail the main request due to memory issues
            self._logger.warning(f"Failed to save conversation to memory: {e}")
            # Don't re-raise - this is a background task
