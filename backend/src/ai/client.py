import json
import logging
import os
import re
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from litellm import acompletion

from src.config.settings import get_settings
from src.core.exceptions import DomainError, ValidationError
from src.core.validators import validate_uuid


# Constants
MIN_LESSON_CONTENT_LENGTH = 100


class AIError(DomainError):
    """Base exception for AI-related errors."""


class RoadmapGenerationError(AIError):
    """Exception raised when roadmap generation fails."""

    def __init__(self, msg: str = "Failed to generate roadmap content") -> None:
        super().__init__(msg)


class NodeCustomizationError(AIError):
    """Exception raised when node customization fails."""

    def __init__(self, msg: str = "Failed to customize node content") -> None:
        super().__init__(msg)


class ExerciseGenerationError(AIError):
    """Exception raised when exercise generation fails."""

    def __init__(self, msg: str = "Failed to generate exercises") -> None:
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
        self.settings = get_settings()
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            msg = "OPENAI_API_KEY not found in environment variables"
            raise ValidationError(msg)

        os.environ["OPENAI_API_KEY"] = self.api_key
        self.model = "openai/gpt-4o"
        self._logger = logging.getLogger(__name__)
        self.memory_wrapper = memory_wrapper

    async def get_completion_with_memory(
        self,
        messages: list[dict[str, str]] | Sequence[dict[str, str]],
        user_id: str | None = None,
        *,
        format_json: bool = True,
        track_interaction: bool = True,
    ) -> str | dict[str, Any] | list[Any]:
        """Get completion with memory integration and tracking."""
        # Build memory context if user_id and memory_wrapper are provided
        if user_id and self.memory_wrapper:
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
                    system_message_idx = next(
                        (i for i, msg in enumerate(messages) if msg.get("role") == "system"), None
                    )

                    memory_prompt = f"Personal Context:\n{memory_context}\n\nPlease use this context to personalize your response appropriately."

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

            except Exception as e:
                self._logger.exception(f"Error integrating memory for user {user_id}: {e}")
                # Continue without memory integration on error

        # Get completion using existing method
        return await self.get_completion(messages, format_json=format_json)

    async def get_completion(
        self,
        messages: list[dict[str, str]] | Sequence[dict[str, str]],
        *,
        format_json: bool = True,
    ) -> str | dict[str, Any] | list[Any]:
        """Get completion from AI model."""
        try:
            if format_json:
                messages = [
                    *list(messages),
                    {
                        "role": "system",
                        "content": "Always respond with valid JSON only, no additional text or markdown, and do not wrap in code fences",
                    },
                ]

            response = await acompletion(
                model=self.model,
                messages=list(messages),  # Convert to list for litellm
                temperature=0.7,
                max_tokens=8000,
            )

            # Extract content from response
            content = str(getattr(response, "choices", [{}])[0].get("message", {}).get("content", ""))
            if not content:
                msg = "No content received from AI model"
                raise AIError(msg)

            if format_json:
                # Clean up JSON response and strip code fences
                content = content.strip()
                # Remove any Markdown code fences
                content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
                content = re.sub(r"\s*```$", "", content, flags=re.IGNORECASE)
            else:
                return content
            return json.loads(content.strip())

        except Exception as e:
            self._logger.exception("Error getting completion from AI")
            msg = f"Failed to generate content: {e!s}"
            raise AIError(msg) from e

    async def generate_onboarding_questions(self, topic: str) -> list[dict[str, Any]]:
        """Generate personalized onboarding questions."""
        from src.ai.prompts import ONBOARDING_QUESTIONS_PROMPT

        prompt = ONBOARDING_QUESTIONS_PROMPT.format(topic=topic)

        messages = [
            {"role": "system", "content": "You are an expert curriculum designer."},
            {"role": "user", "content": prompt},
        ]

        result = await self.get_completion(messages, expect_list=True)
        if not isinstance(result, list):
            msg = "Expected list response from AI model"
            raise AIError(msg)
        return result

    async def generate_roadmap_content(
        self,
        title: str,
        skill_level: str,
        description: str,
        *,
        min_core_topics: int = 4,
        max_core_topics: int = 14,
        sub_min: int = 3,
        sub_max: int = 13,
    ) -> list[dict[str, Any]]:
        """Generate a detailed hierarchical roadmap as JSON.

        Args:
            title: The title of the roadmap
            skill_level: The skill level (beginner, intermediate, advanced)
            description: Description of the roadmap
            min_core_topics: Minimum number of core topics (default: 4)
            max_core_topics: Maximum number of core topics (default: 4)
            sub_min: Minimum number of subtopics per core topic (default: 3)
            sub_max: Maximum number of subtopics per core topic (default: 3)

        The output JSON follows JSON Schema Draft-07 format as specified in the template.
        """
        if min_core_topics > max_core_topics:
            msg = "min_core_topics cannot be greater than max_core_topics"
            raise ValidationError(msg)
        if sub_min > sub_max:
            msg = "sub_min cannot be greater than sub_max"
            raise ValidationError(msg)
        from src.ai.prompts import ROADMAP_GENERATION_PROMPT

        prompt = ROADMAP_GENERATION_PROMPT.format(
            title=title,
            skill_level=skill_level,
            description=description,
        )

        messages = [
            {"role": "system", "content": "You are a curriculum design expert."},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self.get_completion(messages, format_json=True)
            if not isinstance(response, (list, dict)):
                msg = "Invalid response format from AI model"
                raise RoadmapGenerationError(msg)

            # Handle both direct list and coreTopics dictionary format
            if isinstance(response, dict):
                if "coreTopics" in response:
                    response = response["coreTopics"]
                else:
                    msg = "Expected 'coreTopics' key in response dictionary"
                    raise RoadmapGenerationError(msg)

            if not isinstance(response, list):
                msg = "Expected list response from AI model"
                raise RoadmapGenerationError(msg)

            # Ensure proper formatting of node data
            validated_nodes = []
            for i, node in enumerate(response):
                if not isinstance(node, dict):
                    msg = "Expected dict node from AI model"
                    raise RoadmapGenerationError(msg)

                validated_nodes.append(
                    {
                        "title": str(node.get("title", f"Topic {i + 1}")),
                        "description": str(node.get("description", "")),
                        "content": str(node.get("content", "")),
                        "order": i,
                        "prerequisite_ids": [],  # Start with no prerequisites
                        "children": node.get(
                            "subtopics", node.get("children", [])
                        ),  # Handle both subtopics and children
                    },
                )

        except Exception as e:
            self._logger.exception("Error generating roadmap content")
            raise RoadmapGenerationError from e
        else:
            return validated_nodes

    async def generate_practice_exercises(
        self,
        node_id: UUID,
        topic: str,
        difficulty: str,
    ) -> list[dict[str, str]]:
        """Generate practice exercises for a node."""
        if not validate_uuid(node_id):
            msg = "Invalid node ID"
            raise ValidationError(msg)

        from src.ai.prompts import PRACTICE_EXERCISES_PROMPT

        prompt = PRACTICE_EXERCISES_PROMPT.format(
            topic=topic,
            difficulty=difficulty,
        )

        messages = [
            {"role": "system", "content": "You are an expert at creating educational exercises."},
            {"role": "user", "content": prompt},
        ]

        try:
            result = await self.get_completion(messages, expect_list=True)
            if not isinstance(result, list):
                msg = "Expected list response from AI model"
                raise ExerciseGenerationError
            return result
        except Exception as e:
            self._logger.exception("Error generating exercises")
            raise ExerciseGenerationError from e

    async def generate_node_content(
        self,
        roadmap_id: UUID,
        current_node: str,
        progress_level: str,
    ) -> dict[str, Any]:
        """Generate customized content for a new node."""
        if not validate_uuid(roadmap_id):
            msg = "Invalid roadmap ID"
            raise ValidationError(msg)
        from src.ai.prompts import ROADMAP_NODE_CONTENT_PROMPT

        # Build node details and roadmap structure for the prompt
        node_details = {"title": current_node}
        roadmap_json = f"roadmap_id={roadmap_id}, skill_level={progress_level}"
        parent_info = "(parent information not available)"

        prompt = ROADMAP_NODE_CONTENT_PROMPT.format(
            parent_info=parent_info,
            node_details=node_details,
            roadmap_json=roadmap_json,
        )
        messages = [
            {"role": "system", "content": "You are an expert curriculum designer."},
            {"role": "user", "content": prompt},
        ]
        try:
            response = await self.get_completion(messages)
            if not isinstance(response, dict):
                msg = "Expected dict response from AI model"
                raise NodeCustomizationError(msg)

            return {
                "title": str(response.get("title", current_node)),
                "description": str(response.get("description", "")),
                "content": str(response.get("content", "")),
                "prerequisites": response.get("prerequisites", []),
            }
        except Exception as e:
            self._logger.exception("Error generating node content")
            raise NodeCustomizationError from e

    async def generate_content_tags(
        self,
        content_type: str,
        title: str,
        content_preview: str,
    ) -> list[str]:
        """Generate subject-based tags for content using LiteLLM.

        Args:
            content_type: Type of content (book, video, roadmap)
            title: Title of the content
            content_preview: Preview or excerpt of the content

        Returns
        -------
            List of generated tags

        Raises
        ------
            TagGenerationError: If tag generation fails
        """
        from src.ai.prompts import CONTENT_TAGGING_PROMPT

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
            result = await self.get_completion(messages, expect_list=True)
            if not isinstance(result, list):
                msg = "Expected list response from AI model"
                raise TagGenerationError(msg)

            # Normalize tags: lowercase, hyphenated
            normalized_tags = []
            for tag in result:
                if isinstance(tag, str):
                    normalized = tag.lower().strip().replace(" ", "-")
                    # Remove any special characters except hyphens
                    normalized = re.sub(r"[^a-z0-9-]", "", normalized)
                    if normalized:
                        normalized_tags.append(normalized)

            return normalized_tags[:7]  # Limit to max 7 tags

        except Exception as e:
            self._logger.exception("Error generating content tags")
            raise TagGenerationError from e

    async def generate_tags_with_confidence(
        self,
        content_type: str,
        title: str,
        content_preview: str,
    ) -> list[dict[str, Any]]:
        """Generate tags with confidence scores.

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
        from src.ai.prompts import CONTENT_TAGGING_WITH_CONFIDENCE_PROMPT

        prompt = CONTENT_TAGGING_WITH_CONFIDENCE_PROMPT.format(
            content_type=content_type,
            title=title,
            preview=content_preview[:3000],
        )

        messages = [
            {"role": "system", "content": "You are an expert at categorizing educational content."},
            {"role": "user", "content": prompt},
        ]

        try:
            result = await self.get_completion(messages, expect_list=True)
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

            return processed_tags[:7]

        except Exception as e:
            self._logger.exception("Error generating tags with confidence")
            raise TagGenerationError from e


async def create_lesson_body(node_meta: dict[str, Any]) -> str:
    """
    Generate a comprehensive lesson in Markdown format based on node metadata.

    Args:
        node_meta: Dictionary containing metadata about the node, including title,
                  description, and any other relevant information.

    Returns
    -------
        str: Markdown-formatted lesson content.

    Raises
    ------
        LessonGenerationError: If lesson generation fails.
    """
    try:
        # Extract node information
        node_title = node_meta.get("title", "")
        node_description = node_meta.get("description", "")
        skill_level = node_meta.get("skill_level", "beginner")

        from src.ai.prompts import LESSON_GENERATION_PROMPT

        # Create a more detailed prompt for lesson generation
        content_info = f"{node_title} - {node_description} (Skill Level: {skill_level})"
        prompt = LESSON_GENERATION_PROMPT.format(content=content_info)

        messages = [
            {
                "role": "system",
                "content": "You are an expert educator creating high-quality, comprehensive learning materials. Your lessons are detailed, well-structured, and include practical examples and exercises.",
            },
            {"role": "user", "content": prompt},
        ]

        logging.info(f"Generating lesson for '{node_title}' with skill level '{skill_level}'")

        # Get completion without JSON formatting
        response = await acompletion(
            model="openai/gpt-4o",
            messages=messages,
            temperature=0.7,
            max_tokens=8000,
        )

        markdown_content = str(getattr(response, "choices", [{}])[0].get("message", {}).get("content", ""))
        if markdown_content is None:
            raise LessonGenerationError

        if not isinstance(markdown_content, str) or len(markdown_content.strip()) < MIN_LESSON_CONTENT_LENGTH:
            logging.error(
                f"Invalid or too short lesson content received: {markdown_content[:MIN_LESSON_CONTENT_LENGTH]}...",
            )
            raise LessonGenerationError

        logging.info(f"Successfully generated lesson content ({len(markdown_content)} characters)")
        return markdown_content

    except Exception as e:
        logging.exception("Error generating lesson content")
        raise LessonGenerationError from e
