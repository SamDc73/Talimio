import asyncio
import json
import logging
import os
import re
from collections.abc import AsyncGenerator, Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import instructor
from litellm import acompletion
from pydantic import BaseModel, ConfigDict, Field

from src.ai.constants import (
    AI_REQUEST_TIMEOUT,
    MAX_AI_RETRIES,
)
from src.ai.prompts import (
    LESSON_GENERATION_PROMPT,
    ROADMAP_GENERATION_PROMPT,
)
from src.ai.rag.service import RAGService
from src.config.settings import get_settings
from src.database.session import async_session_maker
from src.exceptions import DomainError, ValidationError


class AIError(DomainError):
    """Base exception for AI-related errors."""


class RoadmapGenerationError(AIError):
    """Exception raised when roadmap generation fails."""

    def __init__(self, msg: str = "Failed to generate roadmap content") -> None:
        super().__init__(msg)


class LessonGenerationError(AIError):
    """Exception raised when lesson generation fails."""

    def __init__(self, msg: str = "Failed to generate lesson content") -> None:
        super().__init__(msg)


class TagGenerationError(AIError):
    """Exception raised when tag generation fails."""

    def __init__(self, msg: str = "Failed to generate tags") -> None:
        super().__init__(msg)


# Pydantic models for structured output
class Lesson(BaseModel):
    """Model for lessons within a module."""

    title: str
    description: str

    model_config = ConfigDict(extra="forbid")


class Module(BaseModel):
    """Model for modules in a course."""

    title: str
    description: str
    lessons: list[Lesson] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class CourseStructure(BaseModel):
    """Model for the course/roadmap structure returned by AI."""

    title: str
    description: str
    modules: list[Module] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class ModelManager:
    """Manage AI model interactions for the learning roadmap platform."""

    def __init__(self) -> None:
        """Initialize ModelManager.

        Justification for C901: This initialization method requires handling multiple
        API providers (OpenAI, Anthropic, DeepSeek, OpenRouter) with specific validation
        for each. The complexity is necessary to maintain a clean public API while
        supporting diverse model providers. Further reduction would require breaking
        the single responsibility principle or creating unnecessary abstraction layers.
        """
        from src.config import env

        self.settings = get_settings()
        self.model = env("PRIMARY_LLM_MODEL")
        self._async_memory_manager = None  # Will be lazy-loaded

        # Setup logger first
        self._logger = logging.getLogger(__name__)

        # Default to a sensible model if not configured
        if not self.model:
            self.model = "gpt-4o-mini"
            self._logger.warning("PRIMARY_LLM_MODEL not set, defaulting to gpt-4o-mini")

        # Set appropriate API key based on model provider

        if self.model.startswith("openrouter/"):
            self.api_key = env("OPENROUTER_API_KEY")
            if not self.api_key:
                msg = "OPENROUTER_API_KEY not found in environment variables"
                raise ValidationError(msg)
            os.environ["OPENROUTER_API_KEY"] = self.api_key
        elif self.model.startswith("anthropic/") or self.model.startswith("claude"):
            self.api_key = env("ANTHROPIC_API_KEY")
            if not self.api_key:
                msg = "ANTHROPIC_API_KEY not found in environment variables"
                raise ValidationError(msg)
            os.environ["ANTHROPIC_API_KEY"] = self.api_key
        elif self.model.startswith("deepseek/"):
            self.api_key = env("DEEPSEEK_API_KEY")
            if not self.api_key:
                msg = "DEEPSEEK_API_KEY not found in environment variables"
                raise ValidationError(msg)
            os.environ["DEEPSEEK_API_KEY"] = self.api_key
        else:
            # Default to OpenAI for openai/ models and others
            self.api_key = env("OPENAI_API_KEY")
            if not self.api_key:
                msg = (
                    "OPENAI_API_KEY not found in environment variables. "
                    "Please set OPENAI_API_KEY in your .env file. "
                    "You can get an API key from: https://platform.openai.com/api-keys"
                )
                raise ValidationError(msg)
            # Validate API key format
            if self.api_key.startswith("sk-proj-") and len(self.api_key) > 200:
                msg = (
                    "Invalid OPENAI_API_KEY format detected. "
                    "Please ensure you copied the complete API key correctly. "
                    "API keys should start with 'sk-' and be around 50 characters long."
                )
                raise ValidationError(msg)
            os.environ["OPENAI_API_KEY"] = self.api_key

    async def _get_memory_manager(self) -> Any:
        """Get the async memory manager (lazy-loaded)."""
        if self._async_memory_manager is None:
            from src.ai.memory import get_memory_wrapper

            self._async_memory_manager = await get_memory_wrapper()
        return self._async_memory_manager

    def _inject_memory_into_messages(
        self,
        messages: list[dict[str, str]],
        memory_context: str,
    ) -> list[dict[str, str]]:
        """Inject memory context into the message list."""
        if not memory_context:
            return messages

        messages = list(messages)  # Convert to mutable list

        # Find existing system message or create new one
        system_message_idx = next((i for i, msg in enumerate(messages) if msg.get("role") == "system"), None)

        memory_prompt = f"""Personal Context:
{memory_context}

Please use this context to personalize your response appropriately."""

        if system_message_idx is not None:
            # Append to existing system message
            messages[system_message_idx]["content"] += f"\n\n{memory_prompt}"
        else:
            # Insert new system message at the beginning
            messages.insert(0, {"role": "system", "content": memory_prompt})

        return messages

    def _parse_json_content(self, content: str) -> dict[str, Any] | list[Any]:
        """Parse JSON content from AI response."""
        content = content.strip()
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
        content = re.sub(r"\s*```$", "", content, flags=re.IGNORECASE)
        return json.loads(content.strip())

    def _handle_api_error(self, e: Exception) -> None:
        """Handle API errors with helpful messages."""
        self._logger.exception("Error getting completion from AI")

        if "AuthenticationError" in str(e) or "401" in str(e):
            model_provider = self.model.split("/")[0].upper()
            msg = (
                "AI API authentication failed. Please check your API key configuration:\n"
                f"1. Ensure {model_provider}_API_KEY is set in your .env file\n"
                "2. Verify the API key is valid and not expired\n"
                "3. Check your API account has credits/quota available"
            )
        elif "RateLimitError" in str(e) or "429" in str(e):
            msg = "AI API rate limit exceeded. Please wait and try again."
        elif "InsufficientQuota" in str(e) or "402" in str(e):
            msg = "AI API quota exceeded. Please check your billing or upgrade your plan."
        else:
            msg = f"Failed to generate content: {e!s}"
        raise AIError(msg) from e

    async def _prepare_messages_with_memory(
        self,
        messages: list[dict[str, str]] | Sequence[dict[str, str]],
        user_id: UUID | None = None,
    ) -> list[dict[str, str]]:
        """Prepare messages with memory context.

        This is the single point where memory is integrated into ALL AI calls.
        Requires user_id to be explicitly passed from the calling service.
        If user_id is None, returns messages as-is without memory integration.
        """
        try:
            # Only integrate memory if user_id is explicitly provided
            if not user_id:
                return list(messages)

            # Extract query from last user message for memory search
            user_messages = [msg for msg in messages if msg.get("role") == "user"]
            current_query = user_messages[-1].get("content", "") if user_messages else ""

            if not current_query:
                return list(messages)

            # Get memory context
            memory_manager = await self._get_memory_manager()
            memory_context = await memory_manager.build_memory_context(
                user_id, current_query, limit=5, threshold=0.3
            )

            # Inject memory context into messages
            messages = self._inject_memory_into_messages(list(messages), memory_context)

            # Store the query for future reference
            await memory_manager.add_memory(
                user_id=user_id,
                content=f"User asked: {current_query[:500]}",
                metadata={
                    "interaction_type": "ai_query",
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

            return messages

        except Exception:
            self._logger.exception("Error integrating memory, continuing without it")
            # Graceful degradation - continue without memory on error
            return list(messages)

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        timeout: int = AI_REQUEST_TIMEOUT,  # noqa: ASYNC109
        stream: bool = False,
        response_format: dict[str, str] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
        user_id: UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Central AI completion interface with automatic memory integration.

        This is THE primary method all AI calls go through.
        Memory is automatically integrated unless skip_memory=True.

        Args:
            model: Model to use (defaults to self.model)
            messages: Messages to send
            temperature: Temperature for generation
            max_tokens: Maximum tokens
            timeout: Request timeout
            stream: Whether to stream the response
            response_format: Optional response format
            tools: Optional tools/functions
            tool_choice: Optional tool choice
            user_id: User ID for memory context (optional). Must be explicitly provided to enable memory.
            **kwargs: Additional arguments for litellm
        """
        # Integrate memory when user_id is explicitly provided
        if user_id:
            messages = await self._prepare_messages_with_memory(messages, user_id)

        # Build request parameters
        request_params = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": timeout,
            "stream": stream,
            **kwargs,
        }

        if response_format:
            request_params["response_format"] = response_format
        if tools:
            request_params["tools"] = tools
        if tool_choice:
            request_params["tool_choice"] = tool_choice

        # Make the actual API call
        response = await acompletion(**request_params)

        # Store response in memory if we have user context and it's not streaming
        if not stream and user_id:
            await self._store_response_in_memory(user_id, messages, response)

        return response

    async def _store_response_in_memory(
        self,
        user_id: UUID,
        messages: list[dict[str, str]],
        response: Any,
    ) -> None:
        """Store AI response in memory (non-blocking)."""
        try:
            # Extract response content
            content = ""
            if hasattr(response, "choices") and response.choices:
                message = (
                    response.choices[0].message
                    if hasattr(response.choices[0], "message")
                    else response.choices[0].get("message", {})
                )
                if hasattr(message, "content"):
                    content = message.content
                elif isinstance(message, dict):
                    content = message.get("content", "")

            if content:
                # Get the original query
                user_messages = [msg for msg in messages if msg.get("role") == "user"]
                query = user_messages[-1].get("content", "") if user_messages else ""

                if query:
                    memory_manager = await self._get_memory_manager()
                    await memory_manager.add_memory(
                        user_id=user_id,
                        content=f"Q: {query[:200]}... A: {content[:300]}...",
                        metadata={
                            "interaction_type": "ai_response",
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                    )
        except Exception:
            self._logger.debug("Failed to store response in memory")

    async def _make_completion_request(
        self,
        messages: list[dict[str, str]],
        *,
        response_format: dict[str, str] | None = None,
        max_tokens: int = 4000,
        temperature: float = 0.7,
        timeout: int = AI_REQUEST_TIMEOUT,  # noqa: ASYNC109 - litellm requires timeout param
        user_id: UUID | None = None,
    ) -> str:
        """Make a single completion request to the AI API with automatic memory integration.

        This now delegates to the universal acompletion method.
        """
        response = await self.complete(
            messages,
            response_format=response_format,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
            user_id=user_id,
        )
        return getattr(response, "choices", [{}])[0].get("message", {}).get("content", "")

    def _handle_json_response(self, content: str) -> dict[str, Any] | list[Any]:
        """Handle JSON parsing of response."""
        return self._parse_json_content(content)

    def _handle_text_response(self, content: str | None) -> str:
        """Handle text response."""
        return content or "No response from AI model"

    async def _handle_completion_error(
        self,
        error: Exception,
        attempt: int,
        max_retries: int,
    ) -> bool:
        """Handle various types of errors during completion.

        Returns
        -------
            True if should retry, False otherwise.
        """
        if isinstance(error, json.JSONDecodeError):
            if attempt < max_retries - 1:
                self._logger.warning(
                    "JSON parsing failed on attempt %d/%d. Retrying...",
                    attempt + 1,
                    max_retries,
                )
                return True
            return False

        if isinstance(error, (AttributeError, KeyError)):
            self._logger.exception("Invalid response structure from AI")
            error_msg = f"AI response has unexpected structure: {error!s}"
            raise AIError(error_msg) from error

        if isinstance(error, TimeoutError):
            self._logger.exception("AI request timed out")
            if attempt < max_retries - 1:
                self._logger.info("Retrying after timeout (attempt %d/%d)", attempt + 1, max_retries)
                return True
            error_msg = "AI request timed out after multiple attempts"
            raise AIError(error_msg) from error

        # Handle other API errors
        self._handle_api_error(error)
        return False

    async def get_completion(  # noqa: C901, PLR0912
        # Justification for C901/PLR0912: This method orchestrates multiple complex concerns:
        # 1. Memory integration with user context
        # 2. Function calling support with tool execution
        # 3. Retry logic for transient failures
        # 4. JSON/text response handling with different storage paths
        # 5. Multiple error conditions (JSON, timeout, API errors)
        # The complexity has been minimized by extracting helper methods, but the core
        # orchestration requires these branches to handle all edge cases properly.
        self,
        messages: list[dict[str, str]] | Sequence[dict[str, str]],
        *,
        format_json: bool = True,
        max_retries: int = MAX_AI_RETRIES,
        user_id: UUID | None = None,
        use_memory: bool = True,
        context_type: str | None = None,
        context_id: UUID | None = None,
        context_meta: dict[str, Any] | None = None,
        interaction_type: str = "ai_query",
        store_response: bool = True,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
        max_function_calls: int = 5,
    ) -> str | dict[str, Any] | list[Any]:
        """Get completion from the specified AI model with retry logic and optional function calling.

        This method coordinates memory integration, function calling, API calls, response parsing,
        and error handling. The complexity is managed by delegating to focused helper methods.

        Args:
            messages: Messages to send to the AI
            format_json: Whether to parse response as JSON
            max_retries: Maximum number of retries for API/JSON errors
            user_id: User ID for memory context (optional)
            use_memory: Whether to use memory integration (default: True)
            context_type: Type of context ('book', 'video', 'course', etc.)
            context_id: UUID of the resource
            context_meta: Context metadata (page, timestamp, lesson_id, etc.)
            interaction_type: Type of interaction (assistant_chat, course_creation, etc.)
            store_response: Whether to store the AI response in memory
            tools: List of function schemas in OpenAI format (optional)
            tool_choice: Tool choice strategy ("auto", "none", or specific tool)
            max_function_calls: Maximum number of function calls to prevent loops

        Returns
        -------
            AI response as string, dict, or list
        """
        messages_list = list(messages)
        # Pass user_id to enable memory, or None to disable it
        user_id_for_memory = user_id if use_memory else None

        # Extract user query for potential storage
        user_messages = [msg for msg in messages_list if msg.get("role") == "user"]
        user_query = user_messages[-1].get("content", "") if user_messages else ""

        # Track whether to force JSON mode for the next attempt
        use_json_mode = format_json
        # Step 2: Handle function calling if tools are provided
        if tools and self._supports_function_calling():
            return await self._handle_function_calling(
                messages_list,
                tools,
                tool_choice,
                max_function_calls,
                user_id,
                user_query,
                store_response,
                format_json,
                context_type,
                context_id,
                context_meta,
                interaction_type,
                user_id_for_memory,
            )

        # Step 3: Regular completion without tools
        last_json_error = None
        for attempt in range(max_retries):
            try:
                # Make the API request
                content = await self._make_completion_request(
                    messages_list,
                    response_format={"type": "json_object"} if use_json_mode else None,
                    max_tokens=3000,
                    temperature=0.7,
                    timeout=AI_REQUEST_TIMEOUT,
                    user_id=user_id_for_memory,
                )

                # Handle response based on expected format
                if format_json:
                    if content:
                        try:
                            # Memory storage happens automatically in acompletion
                            return self._handle_json_response(content)
                        except json.JSONDecodeError as json_error:
                            # Parsing failed; retry after disabling forced JSON mode
                            last_json_error = json_error
                            use_json_mode = False
                            should_retry = await self._handle_completion_error(json_error, attempt, max_retries)
                            if should_retry:
                                continue
                            raise
                    else:
                        # Empty content when JSON was expected - retry without forcing JSON mode
                        self._logger.warning(
                            "Empty AI response on attempt %d/%d while expecting JSON; retrying without JSON mode",
                            attempt + 1,
                            max_retries,
                        )
                        use_json_mode = False
                        if attempt < max_retries - 1:
                            continue
                        # Final attempt produced no content; treat as error
                        error_msg = "AI model returned empty response"
                        raise AIError(error_msg)

                # Non-JSON mode: return text response
                # Memory storage happens automatically in acompletion
                return self._handle_text_response(content)

            except json.JSONDecodeError:
                # Already handled above, just reraise on final attempt
                if attempt == max_retries - 1:
                    raise

            except TimeoutError as e:
                should_retry = await self._handle_completion_error(e, attempt, max_retries)
                if should_retry:
                    await asyncio.sleep(2**attempt)  # Exponential backoff
                    continue

            except (AttributeError, KeyError, Exception) as e:
                # These errors don't support retry
                await self._handle_completion_error(e, attempt, max_retries)

        # Handle final errors after all retries
        if last_json_error:
            msg = f"Failed to parse JSON after {max_retries} attempts: {last_json_error!s}"
            raise AIError(msg) from last_json_error

        msg = "Unexpected error: no response received"
        raise AIError(msg)

    def _format_tools_for_api(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Format tools for API compatibility."""
        formatted_tools = []
        for tool in tools:
            if "function" not in tool:
                # Wrap in function key for OpenRouter compatibility
                formatted_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.get("name"),
                            "description": tool.get("description"),
                            "parameters": tool.get("parameters", {}),
                        },
                    }
                )
            else:
                formatted_tools.append(tool)
        return formatted_tools

    async def _handle_function_calling(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        tool_choice: str,
        max_function_calls: int,
        user_id: UUID | None,  # noqa: ARG002
        user_query: str,  # noqa: ARG002
        store_response: bool,  # noqa: ARG002
        format_json: bool,
        context_type: str | None,  # noqa: ARG002
        context_id: UUID | None,  # noqa: ARG002
        context_meta: dict[str, Any] | None,  # noqa: ARG002
        interaction_type: str,  # noqa: ARG002
        user_id_for_memory: UUID | None,
    ) -> str | dict[str, Any] | list[Any]:
        """Handle completion with function calling support."""
        function_call_count = 0

        while function_call_count < max_function_calls:
            try:
                # Make API call with our centralized complete method
                response = await self.complete(
                    messages,
                    temperature=0.7,
                    max_tokens=4000,
                    tools=self._format_tools_for_api(tools),
                    tool_choice=tool_choice,
                    user_id=user_id_for_memory,
                )

                # Extract response
                choice = getattr(response, "choices", [{}])[0]
                message = choice.get("message", {})
                content = message.get("content", "")
                tool_calls = message.get("tool_calls", [])

                # If no tool calls, return final response
                if not tool_calls:
                    # Memory storage now happens automatically in acompletion
                    if format_json and content:
                        return self._parse_json_content(content)
                    return content or "No response from AI model"

                # Process tool calls
                messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})

                # Execute each tool call
                for tool_call in tool_calls:
                    await self._execute_tool_call(tool_call, messages)

                function_call_count += 1

            except Exception as e:
                self._logger.exception("Error in function calling loop")

                # Check if it's a quota error
                if "insufficient_quota" in str(e) or "429" in str(e):
                    msg = "OpenAI API quota exceeded. Please check your OpenAI account billing and usage limits."
                    raise AIError(msg) from e

                # Return error if we've already made function calls
                if function_call_count > 0:
                    return {"error": f"Function calling failed: {e!s}"}

                # Re-raise for first attempt
                raise

        # Max function calls exceeded
        self._logger.warning("Maximum function calls (%s) exceeded", max_function_calls)
        return {"error": "Maximum function calls exceeded"}

    async def _execute_tool_call(self, tool_call: dict[str, Any], messages: list[dict[str, Any]]) -> None:
        """Execute a single tool call and update messages."""
        from src.ai.functions import execute_function

        function_name = tool_call.get("function", {}).get("name")
        function_args_str = tool_call.get("function", {}).get("arguments", "{}")
        tool_call_id = tool_call.get("id", "")

        try:
            # Parse function arguments
            function_args = json.loads(function_args_str)

            # Execute function
            result = await execute_function(function_name, function_args)

            # Add tool response to messages
            messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": json.dumps(result)})

            self._logger.info("Tool call executed: %s", function_name)

        except Exception as e:
            # Add error response to messages
            error_result = {"success": False, "error": str(e), "function_name": function_name}
            messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": json.dumps(error_result)})

            self._logger.exception("Error executing tool call %s", function_name)

    def _supports_function_calling(self) -> bool:
        """Check if the current model supports function calling."""
        return (
            self.model.startswith("openai/")
            or self.model.startswith("gpt-")
            or (
                self.model.startswith("openrouter/")
                and any(provider in self.model for provider in ["openai", "anthropic", "meta"])
            )
        )

    async def get_streaming_completion(
        self,
        messages: list[dict[str, str]] | Sequence[dict[str, str]],
        user_id: UUID | None = None,
    ) -> AsyncGenerator[str, None]:
        """Get streaming completion from AI model with automatic memory integration."""
        try:
            response = await self.complete(
                list(messages),
                temperature=0.7,
                max_tokens=8000,
                stream=True,
                user_id=user_id,
            )

            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            self._logger.exception("Error getting streaming completion from AI")
            msg = f"Failed to generate streaming content: {e!s}"
            raise AIError(msg) from e

    async def _enhance_description_with_tools(self, user_prompt: str, description: str) -> str:
        """Enhance description by discovering content with function calling."""
        self._logger.info("Using function calling to discover content for roadmap generation")
        from src.ai.functions import get_roadmap_functions

        tools = get_roadmap_functions(user_prompt)
        self._logger.info("Available tools for discovery: %s", [t["name"] for t in tools])

        # Build enhanced prompt with function calling
        enhanced_messages = [
            {
                "role": "system",
                "content": "You are a curriculum design expert. Use the content discovery tools to find relevant learning resources and incorporate them into your roadmap design.",
            },
            {
                "role": "user",
                "content": f"Create a comprehensive learning roadmap for '{user_prompt}'. Search for existing courses, YouTube videos, articles, and other resources to inform your curriculum design.",
            },
        ]

        try:
            # Get AI response with tools
            discovery_response = await self.get_completion(
                messages=enhanced_messages, tools=tools, tool_choice="auto", format_json=False
            )
            self._logger.info("Function calling completed successfully")

            # Add discovered content to the original prompt
            return f"{description}\n\nDiscovered Resources:\n{discovery_response}"
        except Exception:
            self._logger.exception("Function calling failed")
            # Continue without function calling on error
            self._logger.info("Continuing without function calling due to error")
            return description

    async def generate_roadmap_content(
        self,
        user_prompt: str,
        description: str = "",
        *,
        use_tools: bool = False,
    ) -> dict[str, Any]:
        """Generate a detailed hierarchical roadmap using Instructor.

        Args:
            user_prompt: The user's learning topic/prompt
            description: Additional context for the roadmap
            use_tools: Enable function calling for content discovery (default: False)

        Returns
        -------
            Dict containing title, description, and modules array
        """
        self._logger.info("Generating roadmap for: %s...", user_prompt[:100])
        self._logger.info("Model: %s, Function calling requested: %s", self.model, use_tools)

        # Enhance description with tools if enabled
        if use_tools and self._supports_function_calling():
            description = await self._enhance_description_with_tools(user_prompt, description)

        try:
            # Get response from AI using Instructor
            prompt = ROADMAP_GENERATION_PROMPT.format(
                user_prompt=user_prompt,
                description=description,
            )

            base_messages = [
                {
                    "role": "system",
                    "content": "You are a curriculum design expert creating comprehensive learning materials.",
                },
                {"role": "user", "content": prompt},
            ]

            # Use Instructor for structured output, but route calls through self.complete
            client = instructor.from_litellm(self.complete)

            result: CourseStructure = await client.chat.completions.create(
                model=self.model,
                response_model=CourseStructure,
                messages=base_messages,
                temperature=0.7,
                max_retries=MAX_AI_RETRIES,
            )

            # Memory storage happens automatically inside self.complete()
            return result.model_dump()

        except Exception as e:
            self._logger.exception("Error generating roadmap content")
            error_msg = f"Failed to generate roadmap content: {e!s}"
            raise RoadmapGenerationError(error_msg) from e

    def _extract_lesson_metadata(self, node_meta: dict[str, Any]) -> dict[str, Any]:
        """Extract and organize lesson metadata from node_meta."""
        return {
            "node_title": node_meta.get("title", ""),
            "node_description": node_meta.get("description", ""),
            "course_id": node_meta.get("course_id"),
            "course_outline": node_meta.get("course_outline", []),
            "current_module_index": node_meta.get("current_module_index", -1),
            "course_title": node_meta.get("course_title", ""),
            "original_user_prompt": node_meta.get("original_user_prompt", ""),
        }

    def _build_course_context(self, metadata: dict[str, Any]) -> str:
        """Build course context string from metadata."""
        content_info = f"{metadata['node_title']} - {metadata['node_description']}"

        # Add original user preferences if available
        if metadata["original_user_prompt"]:
            content_info += f"\n\nOriginal course request: {metadata['original_user_prompt']}"

        # Add course context to help AI understand where this lesson fits
        if metadata["course_outline"]:
            content_info += f"\n\nThis lesson is part of the course: {metadata['course_title']}"
            current_index = metadata["current_module_index"]

            if current_index > 0:
                content_info += "\n\nPrevious topics covered:"
                for i in range(max(0, current_index - 2), current_index):
                    content_info += (
                        f"\n- {metadata['course_outline'][i]['title']}: {metadata['course_outline'][i]['description']}"
                    )

            if current_index < len(metadata["course_outline"]) - 1:
                content_info += "\n\nUpcoming topics:"
                for i in range(current_index + 1, min(len(metadata["course_outline"]), current_index + 3)):
                    content_info += (
                        f"\n- {metadata['course_outline'][i]['title']}: {metadata['course_outline'][i]['description']}"
                    )

        return content_info

    async def _get_rag_context(
        self, course_id: str | None, user_id: str | None, node_title: str, node_description: str
    ) -> tuple[str, list[dict]]:
        """Get RAG context and citations for a lesson."""
        if not course_id or not user_id:
            return "", []

        try:
            rag_service = RAGService()
            lesson_query = f"{node_title} {node_description}"

            async with async_session_maker() as session:
                search_results = await rag_service.search_documents(
                    session=session, user_id=UUID(user_id), course_id=UUID(course_id), query=lesson_query, top_k=5
                )

                if not search_results:
                    return "", []

                # Build context from search results
                context_parts = []
                citations_info = []

                for result in search_results:
                    # Use actual properties from SearchResult schema
                    title = result.metadata.get("title", "Unknown Source")
                    context_parts.append(f"[Source: {title}]\n{result.content}\n")
                    citations_info.append(
                        {
                            "chunk_id": result.chunk_id,
                            "document_title": title,
                            "similarity_score": result.similarity_score,
                        }
                    )

                rag_context = "\n\nReference Materials:\n" + "\n".join(context_parts)
                self._logger.info(
                    "Added RAG context for lesson '%s' from course %s with %s citations",
                    node_title,
                    course_id,
                    len(citations_info),
                )

                return rag_context, citations_info

        except Exception as e:
            self._logger.warning("Failed to get RAG context for lesson generation: %s", e)
            return "", []

    def _analyze_content_preferences(
        self, original_user_prompt: str, course_title: str, _course_id: str | None
    ) -> dict[str, bool]:
        """Analyze user prompt and course title to determine content preferences."""
        preferences = {
            "videos": False,
            "articles": False,
            "hackernews": False,
            "existing_content": False,
            "all_content": False,
        }

        if original_user_prompt:
            prompt_lower = original_user_prompt.lower()

            # Check for video preferences
            video_keywords = [
                "video",
                "videos",
                "youtube",
                "watch",
                "tutorial video",
                "focus on video",
                "video content",
                "video-based",
            ]
            preferences["videos"] = any(keyword in prompt_lower for keyword in video_keywords)

            # Check for article/documentation preferences
            article_keywords = [
                "article",
                "articles",
                "documentation",
                "docs",
                "blog",
                "tutorial",
                "guide",
                "resource",
                "reading",
            ]
            preferences["articles"] = any(keyword in prompt_lower for keyword in article_keywords)

            # Check for technical/developer content
            tech_keywords = ["technical", "developer", "programming", "hackernews", "hacker news", "tech news"]
            preferences["hackernews"] = any(keyword in prompt_lower for keyword in tech_keywords)

            # Check for comprehensive content
            comprehensive_keywords = [
                "comprehensive",
                "all resources",
                "various sources",
                "multiple sources",
                "diverse content",
            ]
            preferences["all_content"] = any(keyword in prompt_lower for keyword in comprehensive_keywords)

            self._logger.info("Original prompt: %s", original_user_prompt)
            self._logger.info("Content preferences: %s", preferences)

        # Also check course title for content hints
        if course_title:
            title_lower = course_title.lower()
            if not preferences["videos"]:
                preferences["videos"] = any(keyword in title_lower for keyword in ["video", "youtube"])
            if not preferences["articles"]:
                preferences["articles"] = any(keyword in title_lower for keyword in ["guide", "documentation"])

        # If no specific preference, enable article discovery by default
        if not any(preferences.values()):
            preferences["articles"] = True
            self._logger.info("No specific content preference found, defaulting to article discovery")

        return preferences

    def _build_discovery_prompts(self, preferences: dict[str, bool], search_query: str) -> str:
        """Build discovery prompt based on content preferences."""
        discovery_prompts = []

        if preferences.get("all_content"):
            discovery_prompts.append(
                f"Find comprehensive learning resources about {search_query} including videos, articles, tutorials, and technical discussions"
            )
        else:
            if preferences.get("videos"):
                discovery_prompts.append(f"Find YouTube videos and video tutorials about {search_query}")
            if preferences.get("articles"):
                discovery_prompts.append(f"Find high-quality articles, guides, and documentation about {search_query}")
            if preferences.get("hackernews"):
                discovery_prompts.append(f"Find technical discussions and developer insights about {search_query}")
            if preferences.get("existing_content"):
                discovery_prompts.append(f"Find existing courses and learning materials about {search_query}")

        return " AND ".join(discovery_prompts) if discovery_prompts else f"Find learning resources about {search_query}"

    def _format_videos_section(self, videos: list[dict[str, Any]]) -> str:
        """Format video resources for discovery prompt."""
        if not videos:
            return ""

        section = "\nYouTube Videos:\n"
        for v in videos[:5]:
            section += f"- {v.get('title', 'Untitled')} by {v.get('channel', 'Unknown')}\n"
        return section

    def _format_articles_section(self, articles: list[dict[str, Any]]) -> str:
        """Format article resources for discovery prompt."""
        if not articles:
            return ""

        section = "\nArticles & Guides:\n"
        for a in articles[:5]:
            section += f"- {a.get('title', 'Untitled')} - {a.get('url', '')}\n"
        return section

    def _format_hackernews_section(self, hn_items: list[dict[str, Any]]) -> str:
        """Format HackerNews discussions for discovery prompt."""
        if not hn_items:
            return ""

        section = "\nTechnical Discussions:\n"
        for item in hn_items[:3]:
            section += f"- {item.get('title', 'Untitled')} ({item.get('points', 0)} points)\n"
        return section

    def _format_discovery_results(self, discovery_result: str | dict[str, Any] | list[Any]) -> str:
        """Format discovery results into a prompt for lesson generation."""
        discovered_content_prompt = "IMPORTANT: Include the following discovered resources in your lesson:\n\n"

        if isinstance(discovery_result, str):
            discovered_content_prompt += discovery_result
        elif isinstance(discovery_result, dict):
            # Handle structured responses
            discovered_content_prompt += self._format_videos_section(discovery_result.get("videos", []))
            discovered_content_prompt += self._format_articles_section(discovery_result.get("articles", []))
            discovered_content_prompt += self._format_hackernews_section(discovery_result.get("hackernews", []))
        elif isinstance(discovery_result, list):
            # Handle list responses (might be a list of resources)
            discovered_content_prompt += str(discovery_result)

        discovered_content_prompt += (
            "\n\nIntegrate these resources naturally into the lesson content, providing context and building upon them."
        )
        return discovered_content_prompt

    def _clean_markdown_content(self, markdown_content: str) -> str:
        """Clean up markdown content by removing code fences and quotes."""
        markdown_content = markdown_content.strip()

        # Remove markdown code fences if the entire content is wrapped
        if markdown_content.startswith("```") and markdown_content.endswith("```"):
            lines = markdown_content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            markdown_content = "\n".join(lines)

        # Remove any quotes that might wrap the entire content
        markdown_content = markdown_content.strip()
        if (markdown_content.startswith('"') and markdown_content.endswith('"')) or (
            markdown_content.startswith("'") and markdown_content.endswith("'")
        ):
            markdown_content = markdown_content[1:-1]

        return markdown_content

    async def _discover_content_with_tools(
        self, node_title: str, node_description: str, preferences: dict[str, bool], messages: list[dict[str, str]]
    ) -> None:
        """Discover content using function calling and add to messages."""
        self._logger.info(
            "Using function calling for lesson '%s' with preferences: %s",
            node_title,
            [k for k, v in preferences.items() if v],
        )

        from src.ai.functions import get_lesson_functions

        search_query = f"{node_title} {node_description}"
        tools = get_lesson_functions(node_title)

        full_discovery_prompt = self._build_discovery_prompts(preferences, search_query)

        discovery_messages = [
            {
                "role": "system",
                "content": "You are helping discover educational content for a lesson. Use all available tools to find relevant resources.",
            },
            {"role": "user", "content": full_discovery_prompt},
        ]

        try:
            discovery_result = await self.get_completion(
                messages=discovery_messages, tools=tools, tool_choice="auto", format_json=False
            )

            if discovery_result:
                discovered_content_prompt = self._format_discovery_results(discovery_result)
                messages.append({"role": "system", "content": discovered_content_prompt})
                self._logger.info("Added content discovery results for lesson '%s'", node_title)

        except Exception as e:
            self._logger.warning("Content discovery failed for lesson '%s': %s", node_title, e)

    async def create_lesson_body(self, node_meta: dict[str, Any]) -> tuple[str, list[dict]]:
        """Generate a comprehensive lesson in Markdown format based on node metadata.

        Includes RAG context from course documents if course_id is provided.
        Optionally includes adaptive context based on user quiz performance.
        Validates MDX content and retries with AI fixes if needed.

        Args:
            node_meta: Dictionary containing metadata about the node, including title,
                      description, course_id (optional), user_id (optional for adaptive),
                      course_id (optional for adaptive), and any other relevant information.

        Returns
        -------
            tuple[str, list[dict]]: Markdown-formatted lesson content and list of citations.

        Raises
        ------
            LessonGenerationError: If lesson generation fails after all retries.
        """
        max_validation_retries = 3

        try:
            # Extract metadata
            metadata = self._extract_lesson_metadata(node_meta)

            # Build course context
            content_info = self._build_course_context(metadata)

            # Get RAG context and citations
            rag_context, citations_info = await self._get_rag_context(
                metadata["course_id"], metadata.get("user_id"), metadata["node_title"], metadata["node_description"]
            )

            # Prepare initial messages - use simple string replacement to avoid curly brace conflicts
            # This is safer than .format() when the content might contain braces
            combined_content = content_info + rag_context
            prompt = LESSON_GENERATION_PROMPT.replace("{content}", combined_content)
            messages = [
                {
                    "role": "system",
                    "content": "You are an expert educator creating high-quality, comprehensive learning materials. Your lessons are detailed, well-structured, and include practical examples and exercises. When reference materials are provided, incorporate them naturally into your lesson content and cite sources appropriately. Pay attention to the course context - consider what students have already learned and what they will learn next to ensure proper knowledge progression and avoid redundancy.\n\nCRITICAL: You are generating content for a lesson that ALREADY HAS A TITLE. The UI displays the title separately. DO NOT start with a # heading that repeats the lesson title. However, you SHOULD use headings (##, ###) to structure your lesson content appropriately. Just don't repeat the main lesson title as the first heading.",
                },
                {"role": "user", "content": prompt},
            ]

            self._logger.info("Generating lesson for '%s'", metadata["node_title"])

            # Analyze content preferences
            content_preferences = self._analyze_content_preferences(
                metadata["original_user_prompt"], metadata["course_title"], metadata["course_id"]
            )

            # Use function calling if any content preference is enabled
            if any(content_preferences.values()):
                await self._discover_content_with_tools(
                    metadata["node_title"], metadata["node_description"], content_preferences, messages
                )

            # Import MDX validation utilities (unified MDX service)
            from src.courses.services.mdx_service import mdx_service

            # Generate and validate content with retries
            validation_attempts = 0
            markdown_content = None
            last_error = None

            while validation_attempts < max_validation_retries:
                validation_attempts += 1

                # Generate or regenerate content
                if validation_attempts == 1:
                    # First attempt - normal generation (now with automatic memory!)
                    response = await self.complete(
                        messages,
                        temperature=0.7,
                        max_tokens=8000,
                    )
                else:
                    # Retry attempt - add error context
                    retry_messages = [
                        *messages,
                        {
                            "role": "system",
                            "content": f"The previously generated content had MDX syntax errors. {last_error}",
                        },
                        {
                            "role": "user",
                            "content": "Please regenerate the lesson content, fixing ALL the MDX syntax errors mentioned above. Pay special attention to closing all tags, ensuring valid JavaScript in expressions, and NOT using template variables.",
                        },
                    ]

                    self._logger.info(
                        f"Retrying lesson generation (attempt {validation_attempts}/{max_validation_retries})"
                    )

                    response = await self.complete(
                        retry_messages,
                        temperature=0.6,  # Lower temperature for fixes
                        max_tokens=8000,
                    )

                markdown_content = str(getattr(response, "choices", [{}])[0].get("message", {}).get("content", ""))
                if markdown_content is None:
                    raise LessonGenerationError

                # Clean up the content
                markdown_content = self._clean_markdown_content(markdown_content)

                if not isinstance(markdown_content, str) or len(markdown_content.strip()) < 10:
                    self._logger.error(
                        "Invalid lesson content received: %s...",
                        markdown_content[:100] if markdown_content else "None",
                    )
                    raise LessonGenerationError

                # Validate MDX content
                is_valid, error_msg = mdx_service.validate_mdx(markdown_content)

                if is_valid:
                    self._logger.info(f"MDX validation passed on attempt {validation_attempts}")
                    break  # Content is valid, exit retry loop
                self._logger.warning(
                    f"MDX validation failed on attempt {validation_attempts}: {error_msg[:200] if error_msg else 'Unknown error'}..."
                )
                last_error = error_msg

                if validation_attempts >= max_validation_retries:
                    # Max retries reached, log but don't fail completely
                    self._logger.error(
                        f"Could not generate valid MDX after {max_validation_retries} attempts. "
                        "Returning content with potential issues."
                    )
                    # Add a warning comment that won't show in rendered MDX
                    markdown_content = (
                        f"<!-- MDX validation warning: Content may have syntax issues -->\n{markdown_content}"
                    )
                    break

            self._logger.info(f"Successfully generated lesson content ({len(markdown_content)} characters)")
            return markdown_content.strip(), citations_info

        except Exception as e:
            self._logger.exception("Error generating lesson content")
            raise LessonGenerationError from e
