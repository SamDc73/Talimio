import json
import logging
import os
from collections.abc import Sequence
from uuid import UUID

from litellm import acompletion

from src.config.settings import get_settings
from src.core.exceptions import DomainError, ValidationError
from src.core.validators import validate_uuid


class AIError(DomainError):
    """Base exception for AI-related errors."""


class RoadmapGenerationError(AIError):
    """Exception raised when roadmap generation fails."""

    def __init__(self) -> None:
        super().__init__("Failed to generate roadmap content")


class NodeCustomizationError(AIError):
    """Exception raised when node customization fails."""

    def __init__(self) -> None:
        super().__init__("Failed to customize node content")


class ExerciseGenerationError(AIError):
    """Exception raised when exercise generation fails."""

    def __init__(self) -> None:
        super().__init__("Failed to generate exercises")


class ModelManager:
    """Manage AI model interactions for the learning roadmap platform."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            msg = "OPENAI_API_KEY not found in environment variables"
            raise ValidationError(msg)

        os.environ["OPENAI_API_KEY"] = self.api_key
        self.model = "gpt-4o"
        self._logger = logging.getLogger(__name__)

    async def _get_completion(self, messages: Sequence[dict[str, str]], format_json: bool = True) -> str | dict:
        """Get completion from AI model."""
        try:
            if format_json:
                messages = [*list(messages), {"role": "system", "content": "Always respond with valid JSON only, no additional text"}]

            response = await acompletion(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
            )

            content: str = response.choices[0].message.content

            if format_json:
                # Clean up JSON response
                content = content.strip()
                content = content.removeprefix("```json")
                content = content.removeprefix("```")
                content = content.removesuffix("```")
                return json.loads(content.strip())

            return content

        except Exception as e:
            self._logger.exception("Error getting completion from AI")
            msg = f"Failed to generate content: {e!s}"
            raise AIError(msg) from e

    async def generate_onboarding_questions(self, topic: str) -> list[dict]:
        """Generate personalized onboarding questions."""
        prompt = f"""For someone wanting to learn {topic}, create 5 questions to understand their:
        1. Current experience level with {topic}
        2. Learning goals
        3. Preferred learning style
        4. Available time commitment
        5. Related skills/background

        Format as JSON array:
        [
            {{
                "question": "What is your current experience with {topic}?",
                "options": ["Complete Beginner", "Some Basic Knowledge", "Intermediate", "Advanced"]
            }}
        ]"""

        messages = [
            {"role": "system", "content": "You are an expert curriculum designer."},
            {"role": "user", "content": prompt},
        ]

        return await self._get_completion(messages)

    async def generate_roadmap_content(
        self,
        title: str,
        skill_level: str,
        description: str,
    ) -> list[dict[str, str | int]]:
        """Generate initial core topics for the learning path."""
        prompt = f"""Create a foundational learning path for {title} at {skill_level} level.
        Generate 3-4 core topics that form the essential foundation.
        For each topic provide:
        {{
            "title": "Main topic name",
            "description": "Brief overview",
            "content": "Learning objectives and key points",
            "order": "Sequential number (0-3)",
            "prerequisites": [] # Empty for initial nodes
        }}

        Focus on core/fundamental concepts that would be required before moving to more advanced topics.
        Organize them in a logical learning sequence.
        """

        messages = [
            {"role": "system", "content": "You are a curriculum design expert."},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self._get_completion(messages)

            # Ensure proper formatting of node data
            validated_nodes = []
            for i, node in enumerate(response):
                validated_nodes.append(
                    {
                        "title": str(node.get("title", f"Topic {i+1}")),
                        "description": str(node.get("description", "")),
                        "content": str(node.get("content", "")),
                        "order": i,
                        "prerequisite_ids": [],  # Start with no prerequisites
                    },
                )

            return validated_nodes

        except Exception as e:
            logger.exception("Error generating roadmap content")
            raise RoadmapGenerationError from e

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

        prompt = f"""Create 3 practice exercises for:
        Topic: {topic}
        Difficulty: {difficulty}

        Include problem statement and solution for each exercise.
        Format as JSON array with 'problem' and 'solution' for each exercise."""

        messages = [
            {"role": "system", "content": "You are an expert at creating educational exercises."},
            {"role": "user", "content": prompt},
        ]

        try:
            return await self._get_completion(messages)
        except Exception as e:
            self._logger.exception("Error generating exercises")
            raise ExerciseGenerationError from e
