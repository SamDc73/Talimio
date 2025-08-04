import json
import logging
import os
import re
from collections.abc import AsyncGenerator, Sequence
from typing import Any
from uuid import UUID

from litellm import acompletion

from src.ai.prompts import (
    CONTENT_TAGGING_PROMPT,
    LESSON_GENERATION_PROMPT,
    ROADMAP_GENERATION_PROMPT,
)
from src.ai.rag.service import RAGService
from src.config.settings import get_settings
from src.core.exceptions import DomainError, ValidationError
from src.database.session import async_session_maker


# Constants
MIN_LESSON_CONTENT_LENGTH = 100


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


class ModelManager:
    """Manage AI model interactions for the learning roadmap platform."""

    def __init__(self, memory_wrapper: Any = None) -> None:
        from src.config import env

        self.settings = get_settings()
        self.model = env("PRIMARY_LLM_MODEL")

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

        self._logger = logging.getLogger(__name__)
        self.memory_wrapper = memory_wrapper

    async def _integrate_memory_context(
        self,
        messages: list[dict[str, str]] | Sequence[dict[str, str]],
        user_id: UUID | None = None,
        track_interaction: bool = True,
    ) -> list[dict[str, str]]:
        """Integrate memory context into messages.

        Args:
            messages: Original messages
            user_id: User ID for memory lookup
            track_interaction: Whether to track this interaction

        Returns
        -------
            Modified messages with memory context integrated
        """
        # Return original messages if no user_id or memory_wrapper
        if not (user_id and self.memory_wrapper):
            return list(messages)

        try:
            # Extract query from last user message for memory search
            user_messages = [msg for msg in messages if msg.get("role") == "user"]
            current_query = user_messages[-1].get("content", "") if user_messages else ""

            # Get memory context
            memory_context = await self.memory_wrapper.build_memory_context(user_id, current_query)

            # Prepend memory context to system message if available
            if memory_context:
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

            # Track the interaction if enabled
            if track_interaction and current_query:
                await self.memory_wrapper.track_learning_interaction(
                    user_id=user_id,
                    interaction_type="ai_query",
                    content=f"User asked: {current_query}",
                    metadata={"model": self.model, "timestamp": "now"},
                )

        except Exception:
            self._logger.exception("Error integrating memory for user %s", user_id)
            # Continue without memory integration on error

        return messages

    async def get_completion_with_memory(
        self,
        messages: list[dict[str, str]] | Sequence[dict[str, str]],
        user_id: UUID | None = None,
        *,
        format_json: bool = True,
        track_interaction: bool = True,
    ) -> str | dict[str, Any] | list[Any]:
        """Get completion with memory integration and tracking."""
        # Integrate memory context
        messages = await self._integrate_memory_context(messages, user_id, track_interaction)

        # Get completion using existing method
        return await self.get_completion(messages, format_json=format_json)

    async def get_completion(
        self,
        messages: list[dict[str, str]] | Sequence[dict[str, str]],
        *,
        format_json: bool = True,
    ) -> str | dict[str, Any] | list[Any]:
        """Get completion from the specified AI model."""
        try:
            response = await acompletion(
                model=self.model,
                messages=list(messages),
                temperature=0.7,
                max_tokens=4000,
            )

            content = getattr(response, "choices", [{}])[0].get("message", {}).get("content", "")

            if format_json and content:
                content = content.strip()
                content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
                content = re.sub(r"\s*```$", "", content, flags=re.IGNORECASE)
                return json.loads(content.strip())

            return content or "No response from AI model"

        except Exception as e:
            self._logger.exception("Error getting completion from AI")
            # Provide more helpful error messages for common issues
            if "AuthenticationError" in str(e) or "401" in str(e):
                msg = (
                    "AI API authentication failed. Please check your API key configuration:\n"
                    f"1. Ensure {self.model.split('/')[0].upper()}_API_KEY is set in your .env file\n"
                    "2. Verify the API key is valid and not expired\n"
                    "3. For OpenAI: keys should start with 'sk-' and be ~50 characters\n"
                    "4. Check your API account has credits/quota available"
                )
            else:
                msg = f"Failed to generate content: {e!s}"
            raise AIError(msg) from e

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

    def _parse_json_response(self, content: str) -> dict[str, Any] | list[Any]:
        """Parse JSON response from content."""
        content = content.strip()
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
        content = re.sub(r"\s*```$", "", content, flags=re.IGNORECASE)
        return json.loads(content.strip())

    async def get_completion_with_tools(
        self,
        messages: list[dict[str, str]] | Sequence[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
        user_id: UUID | None = None,
        *,
        format_json: bool = True,
        track_interaction: bool = True,
        max_function_calls: int = 5,
    ) -> str | dict[str, Any] | list[Any]:
        """Get completion with function calling support.

        Args:
            messages: Conversation messages
            tools: List of function schemas in OpenAI format
            tool_choice: Tool choice strategy ("auto", "none", or specific tool)
            user_id: User ID for memory integration
            format_json: Whether to format response as JSON
            track_interaction: Whether to track interaction for memory
            max_function_calls: Maximum number of function calls to prevent loops

        Returns
        -------
            AI response content (string or parsed JSON)
        """
        # Integrate memory context
        messages = await self._integrate_memory_context(messages, user_id, track_interaction)

        # Convert messages to list for processing
        messages = list(messages)
        function_call_count = 0

        while function_call_count < max_function_calls:
            try:
                # Prepare request parameters
                request_params = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 4000,
                }

                # Add tools if provided and model supports them
                if tools and self._supports_function_calling():
                    request_params["tools"] = self._format_tools_for_api(tools)
                    request_params["tool_choice"] = tool_choice

                # Make API call
                response = await acompletion(**request_params)

                # Extract response content
                choice = getattr(response, "choices", [{}])[0]
                message = choice.get("message", {})
                content = message.get("content", "")
                tool_calls = message.get("tool_calls", [])

                # If no tool calls, return final response
                if not tool_calls:
                    if format_json and content:
                        return self._parse_json_response(content)
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
                    self._logger.exception("API Quota exceeded for model: %s", self.model)
                    self._logger.exception(
                        "OpenAI API quota has been exceeded. Please check your billing at https://platform.openai.com/usage"
                    )
                    msg = "OpenAI API quota exceeded. Please check your OpenAI account billing and usage limits."
                    raise AIError(msg) from e

                # Fallback to regular completion on error
                if function_call_count == 0:
                    return await self.get_completion_with_memory(
                        messages, user_id=user_id, format_json=format_json, track_interaction=False
                    )

                # If we've already made some function calls, return error
                return {"error": f"Function calling failed: {e!s}"}

        # If we've exhausted max function calls, return final response
        self._logger.warning("Maximum function calls (%s) exceeded", max_function_calls)
        return {"error": "Maximum function calls exceeded"}

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
    ) -> AsyncGenerator[str, None]:
        """Get streaming completion from AI model."""
        try:
            response = await acompletion(
                model=self.model,
                messages=list(messages),  # Convert to list for litellm
                temperature=0.7,
                max_tokens=8000,
                stream=True,
            )

            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            self._logger.exception("Error getting streaming completion from AI")
            msg = f"Failed to generate streaming content: {e!s}"
            raise AIError(msg) from e

    async def get_streaming_completion_with_memory(
        self,
        messages: list[dict[str, str]] | Sequence[dict[str, str]],
        user_id: UUID | None = None,
        track_interaction: bool = True,
    ) -> AsyncGenerator[str, None]:
        """Get streaming completion with memory integration."""
        # Integrate memory context
        messages = await self._integrate_memory_context(messages, user_id, track_interaction)

        # Stream the response
        async for chunk in self.get_streaming_completion(messages):
            yield chunk

    async def _enhance_description_with_tools(self, user_prompt: str, skill_level: str, description: str) -> str:
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
                "content": f"Create a comprehensive learning roadmap for '{user_prompt}' at {skill_level} level. Search for existing courses, YouTube videos, articles, and other resources to inform your curriculum design.",
            },
        ]

        try:
            # Get AI response with tools
            discovery_response = await self.get_completion_with_tools(
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

    def _extract_roadmap_data(self, response: dict[str, Any]) -> tuple[str, str, list[dict[str, Any]]]:
        """Extract title, description, and core topics from AI response."""
        roadmap_title = ""
        roadmap_description = ""
        core_topics = []

        if "coreTopics" in response:
            # Extract title and description from the response
            roadmap_title = response.get("title", "")
            roadmap_description = response.get("description", "")
            core_topics = response["coreTopics"]
        elif "core_topics" in response:
            # Handle snake_case variant
            roadmap_title = response.get("title", "")
            roadmap_description = response.get("description", "")
            core_topics = response["core_topics"]
        elif "topics" in response:
            # Handle simplified variant
            roadmap_title = response.get("title", "")
            roadmap_description = response.get("description", "")
            core_topics = response["topics"]
        elif isinstance(response.get("response"), dict):
            # Handle nested response
            inner_response = response["response"]
            if "coreTopics" in inner_response:
                roadmap_title = inner_response.get("title", "")
                roadmap_description = inner_response.get("description", "")
                core_topics = inner_response["coreTopics"]
            else:
                msg = f"Expected 'coreTopics' key in nested response. Got keys: {list(inner_response.keys())}"
                raise RoadmapGenerationError(msg)
        else:
            msg = f"Expected 'coreTopics' key in response dictionary. Got keys: {list(response.keys())}"
            raise RoadmapGenerationError(msg)

        return roadmap_title, roadmap_description, core_topics

    def _validate_and_process_nodes(self, core_topics: list[Any]) -> list[dict[str, Any]]:
        """Validate and process roadmap nodes."""
        if not isinstance(core_topics, list):
            msg = "Expected list for coreTopics"
            raise RoadmapGenerationError(msg)

        validated_nodes = []
        for i, node in enumerate(core_topics):
            if not isinstance(node, dict):
                msg = "Expected dict node from AI model"
                raise RoadmapGenerationError(msg)

            # Process subtopics using helper method
            subtopics = node.get("subtopics", node.get("children", []))
            processed_children = self._process_subtopics(subtopics)

            validated_nodes.append(
                {
                    "title": str(node.get("title", f"Topic {i + 1}")),
                    "description": str(node.get("description", "")),
                    "content": str(node.get("content", "")),
                    "order": i,
                    "prerequisite_ids": [],  # Start with no prerequisites
                    "children": processed_children,
                },
            )

        return validated_nodes

    async def generate_roadmap_content(
        self,
        user_prompt: str,
        skill_level: str,
        description: str = "",
        *,
        min_core_topics: int = 4,
        max_core_topics: int = 14,
        sub_min: int = 3,
        sub_max: int = 13,
        use_tools: bool = False,
    ) -> dict[str, Any]:
        """Generate a detailed hierarchical roadmap as JSON with title and description.

        Args:
            user_prompt: The user's learning topic/prompt
            skill_level: The skill level (beginner, intermediate, advanced)
            description: Additional context for the roadmap
            min_core_topics: Minimum number of core topics (default: 4)
            max_core_topics: Maximum number of core topics (default: 14)
            sub_min: Minimum number of subtopics per core topic (default: 3)
            sub_max: Maximum number of subtopics per core topic (default: 13)
            use_tools: Enable function calling for content discovery (default: False)

        Returns
        -------
            Dict containing title, description, and coreTopics array
        """
        self._logger.info("Generating roadmap for: %s...", user_prompt[:100])
        self._logger.info("Model: %s, Function calling requested: %s", self.model, use_tools)

        if min_core_topics > max_core_topics:
            msg = "min_core_topics cannot be greater than max_core_topics"
            raise ValidationError(msg)
        if sub_min > sub_max:
            msg = "sub_min cannot be greater than sub_max"
            raise ValidationError(msg)

        # If tools enabled, enhance the prompt with discovered content
        if use_tools and self._supports_function_calling():
            description = await self._enhance_description_with_tools(user_prompt, skill_level, description)

        prompt = ROADMAP_GENERATION_PROMPT.format(
            user_prompt=user_prompt,
            skill_level=skill_level,
            description=description,
        )

        # Include JSON instruction in the main prompt for better compliance
        messages = [
            {
                "role": "system",
                "content": "You are a curriculum design expert. You must always respond with valid JSON only, no other text.",
            },
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self.get_completion(messages, format_json=True)
            if not isinstance(response, (list, dict)):
                msg = "Invalid response format from AI model"
                raise RoadmapGenerationError(msg)

            # Log the response to debug
            self._logger.info("AI Response type: %s", type(response))
            self._logger.info(
                "AI Response keys: %s", list(response.keys()) if isinstance(response, dict) else "Not a dict"
            )
            if isinstance(response, dict) and len(str(response)) < 500:
                self._logger.info("AI Response content: %s", response)

            # Handle both direct list and coreTopics dictionary format
            if isinstance(response, dict):
                roadmap_title, roadmap_description, core_topics = self._extract_roadmap_data(response)
            else:
                # Fallback for direct list format
                roadmap_title = ""
                roadmap_description = ""
                core_topics = response

            # Validate and process nodes
            validated_nodes = self._validate_and_process_nodes(core_topics)

        except Exception as e:
            self._logger.exception("Error generating roadmap content")
            raise RoadmapGenerationError from e
        else:
            return {"title": roadmap_title, "description": roadmap_description, "coreTopics": validated_nodes}

    def _process_subtopics(self, subtopics: list[Any]) -> list[dict[str, Any]]:
        """Process and validate subtopics for roadmap nodes.

        Args:
            subtopics: List of subtopic data from AI response

        Returns
        -------
            List of validated subtopic dictionaries
        """
        processed_children = []
        for j, subtopic in enumerate(subtopics):
            if isinstance(subtopic, dict):
                processed_children.append(
                    {
                        "title": str(subtopic.get("title", f"Lesson {j + 1}")),
                        "description": str(subtopic.get("description", "")),
                        "content": str(subtopic.get("content", "")),
                        "order": j,
                        "prerequisite_ids": [],
                        "children": [],  # Lessons don't have children in this implementation
                    }
                )
            elif isinstance(subtopic, str):
                # Handle simple string subtopics
                processed_children.append(
                    {
                        "title": str(subtopic),
                        "description": "",
                        "content": "",
                        "order": j,
                        "prerequisite_ids": [],
                        "children": [],
                    }
                )
        return processed_children

    async def generate_content_tags(
        self,
        content_type: str,
        title: str,
        content_preview: str,
    ) -> list[dict[str, Any]]:
        """Generate subject-based tags with confidence scores for content.

        Args:
            content_type: Type of content (book, video, roadmap)
            title: Title of the content
            content_preview: Preview or excerpt of the content

        Returns
        -------
            List of dicts with 'tag' and 'confidence' keys

        Raises
        ------
            TagGenerationError: If tag generation fails
        """
        prompt = CONTENT_TAGGING_PROMPT.format(
            content_type=content_type,
            title=title,
            preview=content_preview[:3000],  # Limit preview length
        )

        messages = [
            {"role": "system", "content": "You are an expert at categorizing educational content."},
            {"role": "user", "content": prompt},
        ]

        try:
            result = await self.get_completion(messages)
            if not isinstance(result, list):
                msg = "Expected list response from AI model"
                raise TagGenerationError(msg)

            # Process and normalize results
            processed_tags = []
            for item in result:
                if isinstance(item, dict) and "tag" in item:
                    tag = str(item["tag"]).lower().strip().replace(" ", "-")
                    tag = re.sub(r"[^a-z0-9-]", "", tag)
                    confidence = float(item.get("confidence", 0.8))
                    if tag:
                        processed_tags.append(
                            {
                                "tag": tag,
                                "confidence": min(max(confidence, 0.0), 1.0),
                            },
                        )

            return processed_tags[:3]  # Limit to max 7 tags

        except Exception as e:
            self._logger.exception("Error generating content tags")
            raise TagGenerationError from e


def _extract_lesson_metadata(node_meta: dict[str, Any]) -> dict[str, Any]:
    """Extract and organize lesson metadata from node_meta."""
    return {
        "node_title": node_meta.get("title", ""),
        "node_description": node_meta.get("description", ""),
        "skill_level": node_meta.get("skill_level", "beginner"),
        "roadmap_id": node_meta.get("roadmap_id"),
        "course_outline": node_meta.get("course_outline", []),
        "current_module_index": node_meta.get("current_module_index", -1),
        "course_title": node_meta.get("course_title", ""),
        "original_user_prompt": node_meta.get("original_user_prompt", ""),
    }


def _build_course_context(metadata: dict[str, Any]) -> str:
    """Build course context string from metadata."""
    content_info = f"{metadata['node_title']} - {metadata['node_description']} (Skill Level: {metadata['skill_level']})"

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


async def _get_rag_context(roadmap_id: str | None, node_title: str, node_description: str) -> tuple[str, list[dict]]:
    """Get RAG context and citations for a lesson."""
    if not roadmap_id:
        return "", []

    try:
        rag_service = RAGService()
        lesson_query = f"{node_title} {node_description}"

        async with async_session_maker() as session:
            search_results = await rag_service.search_documents(
                session=session, roadmap_id=UUID(roadmap_id), query=lesson_query, top_k=5
            )

            if not search_results:
                return "", []

            # Build context from search results
            context_parts = []
            citations_info = []

            for result in search_results:
                context_parts.append(f"[Source: {result.document_title}]\n{result.chunk_content}\n")
                citations_info.append(
                    {
                        "document_id": result.document_id,
                        "document_title": result.document_title,
                        "similarity_score": result.similarity_score,
                    }
                )

            rag_context = "\n\nReference Materials:\n" + "\n".join(context_parts)
            logging.info(
                "Added RAG context for lesson '%s' from roadmap %s with %s citations",
                node_title,
                roadmap_id,
                len(citations_info),
            )

            return rag_context, citations_info

    except Exception as e:
        logging.warning("Failed to get RAG context for lesson generation: %s", e)
        return "", []


def _analyze_content_preferences(
    original_user_prompt: str, course_title: str, roadmap_id: str | None
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

        logging.info("Original prompt: %s", original_user_prompt)
        logging.info("Content preferences: %s", preferences)

    # Also check course title for content hints
    if course_title:
        title_lower = course_title.lower()
        if not preferences["videos"]:
            preferences["videos"] = any(keyword in title_lower for keyword in ["video", "youtube"])
        if not preferences["articles"]:
            preferences["articles"] = any(keyword in title_lower for keyword in ["guide", "documentation"])

    # TEMPORARY: Force video inclusion for testing
    if str(roadmap_id) == "427f65b4-924f-4d54-a76d-994f06908e31":
        preferences["videos"] = True
        logging.info("FORCING video inclusion for course 427f65b4-924f-4d54-a76d-994f06908e31")

    # If no specific preference, enable article discovery by default
    if not any(preferences.values()):
        preferences["articles"] = True
        logging.info("No specific content preference found, defaulting to article discovery")

    return preferences


def _build_discovery_prompts(preferences: dict[str, bool], search_query: str) -> str:
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


def _format_videos_section(videos: list[dict[str, Any]]) -> str:
    """Format video resources for discovery prompt."""
    if not videos:
        return ""

    section = "\nYouTube Videos:\n"
    for v in videos[:5]:
        section += f"- {v.get('title', 'Untitled')} by {v.get('channel', 'Unknown')}\n"
    return section


def _format_articles_section(articles: list[dict[str, Any]]) -> str:
    """Format article resources for discovery prompt."""
    if not articles:
        return ""

    section = "\nArticles & Guides:\n"
    for a in articles[:5]:
        section += f"- {a.get('title', 'Untitled')} - {a.get('url', '')}\n"
    return section


def _format_hackernews_section(hn_items: list[dict[str, Any]]) -> str:
    """Format HackerNews discussions for discovery prompt."""
    if not hn_items:
        return ""

    section = "\nTechnical Discussions:\n"
    for item in hn_items[:3]:
        section += f"- {item.get('title', 'Untitled')} ({item.get('points', 0)} points)\n"
    return section


def _format_discovery_results(discovery_result: str | dict[str, Any]) -> str:
    """Format discovery results into a prompt for lesson generation."""
    discovered_content_prompt = "IMPORTANT: Include the following discovered resources in your lesson:\n\n"

    if isinstance(discovery_result, str):
        discovered_content_prompt += discovery_result
    elif isinstance(discovery_result, dict):
        # Handle structured responses
        discovered_content_prompt += _format_videos_section(discovery_result.get("videos", []))
        discovered_content_prompt += _format_articles_section(discovery_result.get("articles", []))
        discovered_content_prompt += _format_hackernews_section(discovery_result.get("hackernews", []))

    discovered_content_prompt += (
        "\n\nIntegrate these resources naturally into the lesson content, providing context and building upon them."
    )
    return discovered_content_prompt


def _clean_markdown_content(markdown_content: str) -> str:
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
    node_title: str, node_description: str, preferences: dict[str, bool], messages: list[dict[str, str]]
) -> None:
    """Discover content using function calling and add to messages."""
    logging.info(
        "Using function calling for lesson '%s' with preferences: %s",
        node_title,
        [k for k, v in preferences.items() if v],
    )

    from src.ai.functions import get_lesson_functions

    model_manager = ModelManager()
    search_query = f"{node_title} {node_description}"
    tools = get_lesson_functions(node_title)

    full_discovery_prompt = _build_discovery_prompts(preferences, search_query)

    discovery_messages = [
        {
            "role": "system",
            "content": "You are helping discover educational content for a lesson. Use all available tools to find relevant resources.",
        },
        {"role": "user", "content": full_discovery_prompt},
    ]

    try:
        discovery_result = await model_manager.get_completion_with_tools(
            messages=discovery_messages, tools=tools, tool_choice="auto", format_json=False
        )

        if discovery_result:
            discovered_content_prompt = _format_discovery_results(discovery_result)
            messages.append({"role": "system", "content": discovered_content_prompt})
            logging.info("Added content discovery results for lesson '%s'", node_title)

    except Exception as e:
        logging.warning("Content discovery failed for lesson '%s': %s", node_title, e)


async def create_lesson_body(node_meta: dict[str, Any]) -> tuple[str, list[dict]]:
    """Generate a comprehensive lesson in Markdown format based on node metadata.

    Includes RAG context from roadmap documents if roadmap_id is provided.

    Args:
        node_meta: Dictionary containing metadata about the node, including title,
                  description, roadmap_id (optional) and any other relevant information.

    Returns
    -------
        tuple[str, list[dict]]: Markdown-formatted lesson content and list of citations.

    Raises
    ------
        LessonGenerationError: If lesson generation fails.
    """
    try:
        # Extract metadata
        metadata = _extract_lesson_metadata(node_meta)

        # Build course context
        content_info = _build_course_context(metadata)

        # Get RAG context and citations
        rag_context, citations_info = await _get_rag_context(
            metadata["roadmap_id"], metadata["node_title"], metadata["node_description"]
        )

        # Prepare initial messages
        prompt = LESSON_GENERATION_PROMPT.format(content=content_info + rag_context)
        messages = [
            {
                "role": "system",
                "content": "You are an expert educator creating high-quality, comprehensive learning materials. Your lessons are detailed, well-structured, and include practical examples and exercises. When reference materials are provided, incorporate them naturally into your lesson content and cite sources appropriately. Pay attention to the course context - consider what students have already learned and what they will learn next to ensure proper knowledge progression and avoid redundancy.\n\nIMPORTANT: You are generating content for a specific lesson that already has a title and description. DO NOT regenerate or modify the lesson title or description - focus only on creating the lesson content that matches the given title and description.",
            },
            {"role": "user", "content": prompt},
        ]

        logging.info(
            "Generating lesson for '%s' with skill level '%s'", metadata["node_title"], metadata["skill_level"]
        )

        # Analyze content preferences
        content_preferences = _analyze_content_preferences(
            metadata["original_user_prompt"], metadata["course_title"], metadata["roadmap_id"]
        )

        # Use function calling if any content preference is enabled
        if any(content_preferences.values()):
            await _discover_content_with_tools(
                metadata["node_title"], metadata["node_description"], content_preferences, messages
            )

        # Generate lesson content
        from src.config import env

        response = await acompletion(
            model=env("PRIMARY_LLM_MODEL"),
            messages=messages,
            temperature=0.7,
            max_tokens=8000,
        )

        markdown_content = str(getattr(response, "choices", [{}])[0].get("message", {}).get("content", ""))
        if markdown_content is None:
            raise LessonGenerationError

        # Clean up the content
        markdown_content = _clean_markdown_content(markdown_content)

        if not isinstance(markdown_content, str) or len(markdown_content.strip()) < MIN_LESSON_CONTENT_LENGTH:
            logging.error(
                "Invalid or too short lesson content received: %s...",
                markdown_content[:MIN_LESSON_CONTENT_LENGTH],
            )
            raise LessonGenerationError

        logging.info("Successfully generated lesson content (%s characters)", len(markdown_content))
        return markdown_content.strip(), citations_info

    except Exception as e:
        logging.exception("Error generating lesson content")
        raise LessonGenerationError from e
