import asyncio
import json
import logging
import re
from typing import TYPE_CHECKING, Any
from uuid import UUID


if TYPE_CHECKING:
    from src.auth.context import AuthContext

import litellm
from pydantic import BaseModel

from src.ai.models import CourseStructure, ExecutionPlan, LessonContent
from src.ai.prompts import (
    E2B_EXECUTION_SYSTEM_PROMPT,
    LESSON_GENERATION_PROMPT,
    MDX_ERROR_FIX_PROMPT,
    MEMORY_CONTEXT_SYSTEM_PROMPT,
    ROADMAP_GENERATION_PROMPT,
)
from src.config.settings import get_settings


class LLMClient:
    """Manages LLM completion requests with memory integration and RAG support."""

    def __init__(self, rag_service: Any | None = None) -> None:
        """Initialize LLMClient.

        Args:
            rag_service: Optional RAGService instance for dependency injection.
                        If not provided, RAG functionality will be skipped or create a new instance.
        """
        self._logger = logging.getLogger(__name__)
        self._rag_service = rag_service

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

            return await litellm.acompletion(**kwargs)

        except Exception as e:
            self._logger.exception("Error in model completion")
            msg = f"Model completion failed: {e}"
            raise RuntimeError(msg) from e

    async def get_completion(  # noqa: C901
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

            # Handle structured output - use instructor with native async litellm
            if response_model:
                settings = get_settings()
                request_model = model or settings.primary_llm_model

                import instructor
                from litellm import acompletion

                try:
                    # Create instructor client from async litellm
                    client = instructor.from_litellm(acompletion)

                    # Build kwargs for instructor
                    instructor_kwargs = {
                        "model": request_model,
                        "messages": messages,
                        "response_model": response_model,
                        "temperature": temperature if temperature is not None else settings.ai_temperature_default,
                        "max_retries": 3,  # Add retries for resilience
                    }

                    # Only add max_tokens if explicitly provided
                    if max_tokens is not None:
                        instructor_kwargs["max_tokens"] = max_tokens

                    result = await client.chat.completions.create(**instructor_kwargs)

                    # Save conversation to memory (non-blocking)
                    if user_id and result:
                        asyncio.create_task(  # noqa: RUF006
                            self._save_conversation_to_memory(user_id, messages, result)
                        )

                    return result

                except Exception as api_error:
                    self._logger.exception(f"Instructor+litellm call failed: {api_error}")
                    msg = f"Failed to generate structured completion: {api_error}"
                    raise RuntimeError(msg) from api_error

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

    async def _inject_memory_into_messages(
        self, messages: list[dict[str, Any]], user_id: str | UUID
    ) -> list[dict[str, Any]]:
        """Inject user memory context into the conversation."""
        try:
            # Get user memory
            from src.ai.memory import get_memories

            # Normalize user_id to UUID
            normalized_user_id: UUID = user_id if isinstance(user_id, UUID) else UUID(str(user_id))

            memories = await get_memories(user_id=normalized_user_id, limit=10)

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

    async def _handle_function_calling(
        self,
        response: Any,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],  # noqa: ARG002
        temperature: float,
        max_tokens: int,
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

    async def generate_course_structure(self, user_prompt: str, user_id: str | UUID | None = None) -> CourseStructure:
        """Generate a structured learning course using LiteLLM structured output (Pydantic)."""
        try:
            messages = [
                {"role": "system", "content": ROADMAP_GENERATION_PROMPT},
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
            msg = "Failed to generate roadmap content"
            raise RuntimeError(msg) from e

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
                metadata["course_id"],
                metadata["node_title"],
                metadata["node_description"],
                auth,
            )

            # Prepare prompt
            combined_content = content_info + rag_context
            prompt = LESSON_GENERATION_PROMPT.replace("{content}", combined_content)
            messages = [{"role": "user", "content": prompt}]

            # Generate lesson content
            settings = get_settings()
            response = await self.complete(
                messages,
                temperature=settings.ai_temperature_default,
                user_id=metadata.get("user_id"),
            )

            # Get content from response (litellm standard format)
            content = response.choices[0].message.content

            if not content or len(content.strip()) < 100:
                msg = f"Generated content too short: {len(content)} chars"
                raise ValueError(msg)

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

            # Let mem0 handle everything - extraction, deduplication, relevance filtering
            await add_memory(
                user_id=UUID(str(user_id)) if isinstance(user_id, str) else user_id,
                content=conversation
            )

        except Exception as e:
            # Never fail the main request due to memory issues
            self._logger.warning(f"Failed to save conversation to memory: {e}")
            # Don't re-raise - this is a background task
