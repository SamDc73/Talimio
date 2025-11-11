import asyncio
import importlib
import copy
import json
import logging
import re
from typing import TYPE_CHECKING, Any
from uuid import UUID


if TYPE_CHECKING:
    from src.auth.context import AuthContext

import litellm
from pydantic import BaseModel

from src.ai import AGENT_ID_DEFAULT
from src.ai.models import (
    AdaptiveCoursePlan,
    AdaptiveCoursePlanSchema,
    CourseStructure,
    CourseStructureSchema,
    ExecutionPlan,
    LessonContent,
    SelfAssessmentQuiz,
)


SCHEMA_OVERRIDES: dict[type[BaseModel], type[BaseModel]] = {
    CourseStructure: CourseStructureSchema,
    AdaptiveCoursePlan: AdaptiveCoursePlanSchema,
}

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

    async def complete(
        self,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
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
                "temperature": temperature if temperature is not None else settings.ai_temperature_default,
                "timeout": settings.ai_request_timeout,
            }

            # Only add max_tokens if explicitly provided - let model decide otherwise
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens

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
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
        format_json: bool = False,
        user_id: str | UUID | None = None,
        model: str | None = None,
    ) -> Any:
        """Get completion with optional memory integration and structured output."""
        try:
            # Inject memory context if user_id provided
            if user_id:
                messages = await self._inject_memory_into_messages(messages, user_id)

            # Handle structured output via LiteLLM json schema with Instructor fallback
            if response_model:
                settings = get_settings()
                request_model = model or settings.primary_llm_model
                schema_model = SCHEMA_OVERRIDES.get(response_model, response_model)

                try:
                    schema_instance = await self._complete_with_litellm_schema(
                        messages=messages,
                        schema_model=schema_model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        user_id=user_id,
                        model=request_model,
                    )
                    if schema_model is response_model:
                        result = schema_instance
                    else:
                        result = response_model(**schema_instance.model_dump())
                except Exception:
                    self._logger.warning(
                        "LiteLLM structured output failed on model %s; falling back to Instructor",
                        request_model,
                        exc_info=True,
                    )
                    result = await self._complete_with_instructor(
                        messages=messages,
                        response_model=response_model,
                        temperature=temperature,
                        temperature_default=settings.ai_temperature_default,
                        max_tokens=max_tokens,
                        model=request_model,
                        request_timeout=settings.ai_request_timeout,
                    )

                if user_id and result:
                    asyncio.create_task(  # noqa: RUF006
                        self._save_conversation_to_memory(user_id, messages, result)
                    )

                return result

            # Handle function calling
            if tools:
                response = await self.complete(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                    tool_choice=tool_choice,
                    user_id=user_id,
                )

                # Process function calls
                if response.choices[0].message.tool_calls:
                    return await self._handle_function_calling(
                        response, messages, tools, temperature, max_tokens, user_id
                    )

                return response.choices[0].message.content

            # Regular completion (optionally request strict JSON when format_json=True)
            response = await self.complete(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                user_id=user_id,
                response_format={"type": "json_object"} if format_json else None,
                model=model,
            )

            content = response.choices[0].message.content

            # Save conversation to memory (non-blocking)
            if user_id and response:
                asyncio.create_task(  # noqa: RUF006
                    self._save_conversation_to_memory(user_id, messages, content)
                )

            # Handle JSON parsing if requested
            if format_json:
                return self._parse_json_content(content)

            return content

        except Exception as e:
            self._logger.exception("Error in get_completion")
            msg = f"Completion failed: {e}"
            raise RuntimeError(msg) from e

    async def _complete_with_litellm_schema(
        self,
        *,
        messages: list[dict[str, Any]],
        schema_model: type[BaseModel],
        temperature: float | None,
        max_tokens: int | None,
        user_id: str | UUID | None,
        model: str,
    ) -> BaseModel:
        last_error: Exception | None = None
        for attempt in range(2):
            response = await self.complete(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                user_id=user_id,
                response_format=self._build_response_format(schema_model),
                model=model,
            )
            try:
                return self._coerce_response_model(response, schema_model)
            except Exception as parse_error:
                last_error = parse_error
                self._logger.warning(
                    "Structured response validation failed on attempt %s: %s",
                    attempt + 1,
                    parse_error,
                )
        if last_error is None:
            msg = "Structured response validation failed"
            raise RuntimeError(msg)
        raise last_error

    async def _complete_with_instructor(
        self,
        *,
        messages: list[dict[str, Any]],
        response_model: type[BaseModel],
        temperature: float | None,
        temperature_default: float,
        max_tokens: int | None,
        model: str,
        request_timeout: int,
    ) -> BaseModel:
        import instructor
        from litellm import acompletion

        client = instructor.from_litellm(acompletion)
        instructor_kwargs = {
            "model": model,
            "messages": messages,
            "response_model": response_model,
            "temperature": temperature if temperature is not None else temperature_default,
            "max_retries": 3,
            "timeout": request_timeout,
        }
        if max_tokens is not None:
            instructor_kwargs["max_tokens"] = max_tokens

        return await asyncio.wait_for(
            client.chat.completions.create(**instructor_kwargs),
            timeout=request_timeout,
        )

    def _build_response_format(self, response_model: type[BaseModel]) -> dict[str, Any]:
        schema = copy.deepcopy(response_model.model_json_schema())
        self._normalize_json_schema(schema)
        return {
            "type": "json_schema",
            "json_schema": {
                "name": response_model.__name__,
                "schema": schema,
            },
        }

    def _normalize_json_schema(self, node: Any) -> None:
        if not isinstance(node, dict):
            return

        definitions = node.get("$defs") or node.get("definitions")
        if isinstance(definitions, dict):
            for child in definitions.values():
                self._normalize_json_schema(child)

        props = node.get("properties")
        if isinstance(props, dict) and props:
            node["required"] = list(props.keys())
            if "additionalProperties" not in node:
                node["additionalProperties"] = False
            for child in props.values():
                self._normalize_json_schema(child)

        items = node.get("items")
        if isinstance(items, dict):
            self._normalize_json_schema(items)
        elif isinstance(items, list):
            for child in items:
                self._normalize_json_schema(child)

        for key in ("allOf", "anyOf", "oneOf"):
            variants = node.get(key)
            if isinstance(variants, list):
                for child in variants:
                    self._normalize_json_schema(child)

    def _coerce_response_model(
        self,
        raw_response: Any,
        response_model: type[BaseModel],
    ) -> BaseModel:
        model_instance = self._try_convert_payload(raw_response, response_model)
        if model_instance is not None:
            return model_instance

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
                if isinstance(item, dict)
                and item.get("type") == "text"
                and isinstance(item.get("text"), str)
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
            return response_model(**data)
        except Exception:
            return None

    async def _inject_memory_into_messages(
        self, messages: list[dict[str, Any]], user_id: str | UUID
    ) -> list[dict[str, Any]]:
        """Inject user memory context into the conversation."""
        try:
            # Get user memory
            from src.ai.memory import search_memories

            # Normalize user_id to UUID
            normalized_user_id: UUID = user_id if isinstance(user_id, UUID) else UUID(str(user_id))

            query_text = self._build_memory_query(messages)
            if not query_text:
                return messages

            run_id, has_run_scope = self._get_run_scope_state()
            run_filter = run_id if has_run_scope else None
            memories = await search_memories(
                user_id=normalized_user_id,
                query=query_text,
                limit=6,
                agent_id=self._agent_id,
                run_id=run_filter,
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

    def _get_trace_context(self) -> Any | None:
        """Return the active diagnostics trace if available."""
        try:
            trace_module = importlib.import_module("src.diagnostics.trace")
        except ModuleNotFoundError:
            return None
        get_trace = getattr(trace_module, "get_trace", None)
        if callable(get_trace):
            return get_trace()
        return None

    def _get_run_scope_state(self) -> tuple[str | None, bool]:
        """Return the current run identifier and whether this agent already saved memories."""
        trace = self._get_trace_context()
        if trace is None:
            return None, False
        has_scope = getattr(trace, "has_memory_scope", None)
        if callable(has_scope):
            return trace.id, bool(has_scope(self._agent_id))
        return trace.id, False

    def _mark_run_scope(self, run_id: str | None) -> None:
        """Mark that this agent persisted memories for the current run."""
        if not run_id:
            return
        trace = self._get_trace_context()
        if trace is None:
            return
        mark_scope = getattr(trace, "mark_memory_scope", None)
        if callable(mark_scope):
            mark_scope(self._agent_id)

    async def _handle_function_calling(
        self,
        response: Any,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],  # noqa: ARG002
        temperature: float | None,
        max_tokens: int | None,
        user_id: str | UUID | None,
    ) -> str:
        """Handle function calling responses."""
        from src.ai.functions import execute_function

        # Add assistant message with tool calls
        assistant_message = response.choices[0].message
        messages.append(
            {
                "role": "assistant",
                "content": assistant_message.content or "",
                "tool_calls": [tc.dict() for tc in assistant_message.tool_calls],
            }
        )

        # Execute all function calls concurrently
        tool_calls = assistant_message.tool_calls
        function_tasks = [execute_function(tc.function.name, tc.function.arguments) for tc in tool_calls]

        function_results = await asyncio.gather(*function_tasks, return_exceptions=True)

        # Add function results to messages
        for _i, (tool_call, result) in enumerate(zip(tool_calls, function_results, strict=False)):
            if isinstance(result, Exception):
                result_content = f"Error: {result!s}"
                self._logger.error(f"Function {tool_call.function.name} failed: {result}")
            else:
                result_content = str(result)

            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": result_content})

        # Get final response
        final_response = await self.complete(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            user_id=user_id,
        )

        return final_response.choices[0].message.content

    def _parse_json_content(self, content: str) -> dict[str, Any] | list[Any] | str:
        """Parse JSON content from AI response."""
        try:
            # Look for JSON blocks
            json_match = re.search(r"```json\s*\n(.*?)\n```", content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))

            # Try parsing the entire content as JSON
            content_stripped = content.strip()
            if content_stripped.startswith(("{", "[")):
                return json.loads(content_stripped)

            return content

        except json.JSONDecodeError:
            self._logger.warning("Failed to parse JSON content, returning as string")
            return content

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

    async def generate_course_structure(
        self,
        user_prompt: str,
        user_id: str | UUID | None = None,
        *,
        system_prompt: str | None = None,
    ) -> CourseStructure:
        """Generate a structured learning course using LiteLLM structured output (Pydantic)."""
        try:
            prompt = system_prompt or COURSE_GENERATION_PROMPT
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_prompt},
            ]

            # Use structured output via LiteLLM response_format with a Pydantic model
            result = await self.get_completion(
                messages,
                response_model=CourseStructure,
                temperature=0.7,
                user_id=user_id,
            )

            if not isinstance(result, CourseStructure):
                msg = "Expected CourseStructure from structured output"
                raise TypeError(msg)

            return result

        except Exception as e:
            self._logger.exception("Error generating course structure")
            msg = "Failed to generate course outline"
            raise RuntimeError(msg) from e

    async def generate_adaptive_course_from_prompt(
        self,
        *,
        user_goal: str,
        self_assessment_context: str | None = None,
        max_nodes: int = 32,
        max_prereqs: int = 3,
        max_layers: int = 12,
        max_lessons: int = 96,
        user_id: str | UUID | None = None,
    ) -> AdaptiveCoursePlan:
        """Generate the unified adaptive course payload used by ConceptFlow."""
        goal_text = user_goal.strip()
        if not goal_text:
            msg = "User goal must not be empty"
            raise ValueError(msg)

        assessment_block = (
            self_assessment_context.strip() if self_assessment_context else "No self-assessment provided."
        )
        system_prompt = ADAPTIVE_COURSE_GENERATION_PROMPT.substitute(
            user_goal=goal_text,
            self_assessment_context=assessment_block,
            max_nodes=max_nodes,
            max_prereqs=max_prereqs,
            max_layers=max_layers,
            max_lessons=max_lessons,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": "Produce the adaptive course plan JSON exactly as specified.",
            },
        ]

        class _LiteLLMCompletionFilter(logging.Filter):
            """Filter to suppress duplicate LiteLLM completion logs for this call."""

            def __init__(self) -> None:
                super().__init__()
                self._seen: set[str] = set()

            def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
                name = record.name.lower()
                if name != "litellm":
                    return True
                message = record.getMessage()
                if "LiteLLM completion()" not in message:
                    return True
                if message in self._seen:
                    return False
                self._seen.add(message)
                return True

        log_filter = _LiteLLMCompletionFilter()
        target_loggers = [logging.getLogger("LiteLLM"), logging.getLogger("litellm")]
        for target in target_loggers:
            target.addFilter(log_filter)

        try:
            result = await self.get_completion(
                messages,
                response_model=AdaptiveCoursePlan,
                temperature=0.2,
                user_id=user_id,
            )

            if not isinstance(result, AdaptiveCoursePlan):
                msg = "Adaptive course structured response failed"
                raise TypeError(msg)

            return result

        except Exception as e:
            self._logger.exception("Error generating adaptive course plan")
            msg = "Failed to generate adaptive course plan"
            raise RuntimeError(msg) from e
        finally:
            for target in target_loggers:
                try:
                    target.removeFilter(log_filter)
                except ValueError:
                    continue

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
                temperature=0.4,
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
                lines = ["## Target Concept", f"Name: {t_name}" if t_name else None, f"Description: {t_desc}" if t_desc else None]
                if isinstance(t_mastery, (int, float)):
                    lines.append(f"Current mastery: {float(t_mastery):.2f}")
                target_section = "\n".join([ln for ln in lines if ln]) + "\n\n"

            # Prepare prompt
            combined_content = (content_info + target_section + rag_context).strip()
            if not combined_content:
                combined_content = (
                    f"Lesson Title: {title}\n"
                    f"Lesson Topic: {metadata['node_description'] or title}"
                )

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
            settings = get_settings()
            response = await self.complete(
                messages,
                temperature=settings.ai_temperature_default,
                max_tokens=settings.ai_max_tokens_default,
                user_id=metadata.get("user_id"),
            )

            # Get content from response (litellm standard format)
            content = response.choices[0].message.content or ""

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
                    fix_response = await self.complete(
                        fix_messages,
                        temperature=0.3,  # Low temp for accuracy
                        user_id=metadata.get("user_id"),
                    )
                    content = fix_response.choices[0].message.content
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

        messages = [
            {"role": "system", "content": E2B_EXECUTION_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
        ]

        try:
            plan = await self.get_completion(
                messages,
                response_model=ExecutionPlan,
                temperature=0.1,
                max_tokens=2000,
                user_id=user_id,
            )

            if not isinstance(plan, ExecutionPlan):
                msg = "Expected ExecutionPlan from structured output"
                raise TypeError(msg)

            return plan

        except Exception as exc:  # pragma: no cover - surfaced to caller
            self._logger.exception("Failed to generate execution plan")
            msg = "Execution planning failed"
            raise RuntimeError(msg) from exc

    async def _save_conversation_to_memory(
        self, user_id: str | UUID, messages: list[dict[str, Any]], response: Any
    ) -> None:
        """Save conversation to memory using mem0.

        This runs async in background - never blocks the user response.
        mem0 handles all the intelligent extraction, deduplication, and preference detection.
        """
        try:
            from src.ai.memory import add_memory

            # Extract the user's last message
            user_message = messages[-1].get("content", "") if messages else ""

            # Handle different response types
            if isinstance(response, str):
                ai_response = response[:1000]  # Limit to first 1000 chars
            elif hasattr(response, "model_dump"):
                # Pydantic model (structured output)
                ai_response = str(response.model_dump())[:1000]
            elif hasattr(response, "choices"):
                # Raw completion response
                ai_response = response.choices[0].message.content[:1000] if response.choices else ""
            else:
                ai_response = str(response)[:1000]

            # Combine into conversation format
            conversation = f"User: {user_message}\nAssistant: {ai_response}"

            normalized_user_id = UUID(str(user_id)) if isinstance(user_id, str) else user_id
            run_id, _ = self._get_run_scope_state()
            metadata = {
                "agent_id": self._agent_id,
            }
            if run_id:
                metadata["run_id"] = run_id

            # Let mem0 handle everything - extraction, deduplication, relevance filtering
            await add_memory(
                user_id=normalized_user_id,
                content=conversation,
                agent_id=self._agent_id,
                run_id=run_id,
                metadata=metadata,
            )
            self._mark_run_scope(run_id)

        except Exception as e:
            # Never fail the main request due to memory issues
            self._logger.warning(f"Failed to save conversation to memory: {e}")
            # Don't re-raise - this is a background task
