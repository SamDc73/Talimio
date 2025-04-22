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

    async def _get_completion(self, messages: Sequence[dict[str, str]], *, format_json: bool = True) -> str | dict:
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
                messages=messages,
                temperature=0.7,
                max_tokens=8000,
            )

            content: str = response.choices[0].message.content

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
    ) -> list[dict[str, Any]]:
        """Generate a detailed hierarchical roadmap as JSON."""
        prompt = f"""
You are a curriculum design expert. Generate a hierarchical learning path as a pure JSON array for the new roadmap:
  Title: {title}
  Description: {description}
  Skill Level: {skill_level}
Requirements:
 - Exactly 4 core topics (level 1)
 - Each core topic must have exactly 3 subtopics (level 2)
 - Each subtopic must have exactly 2 sub-subtopics (level 3)
Use this exact node schema and follow the example structure:

Example output:
[
  {{
    "title": "Core Topic 1",
    "description": "Overview of Core Topic 1",
    "content": "Key learning objectives...",
    "order": 0,
    "prerequisite_ids": [],
    "children": [
      {{
        "title": "Subtopic 1.1",
        "description": "Overview of Subtopic 1.1",
        "content": "Objectives...",
        "order": 0,
        "prerequisite_ids": [],
        "children": [
          {{
            "title": "Sub-subtopic 1.1.1",
            "description": "Details of Sub-subtopic 1.1.1",
            "content": "Objectives...",
            "order": 0,
            "prerequisite_ids": [],
            "children": []
          }},
          {{
            "title": "Sub-subtopic 1.1.2",
            "description": "Details of Sub-subtopic 1.1.2",
            "content": "Objectives...",
            "order": 1,
            "prerequisite_ids": [],
            "children": []
          }}
        ]
      }},
      {{ "title": "Subtopic 1.2", "description": "...", "content": "...", "order": 1, "prerequisite_ids": [], "children": [/* 2 sub-subtopics */] }},
      {{ "title": "Subtopic 1.3", "description": "...", "content": "...", "order": 2, "prerequisite_ids": [], "children": [/* 2 sub-subtopics */] }}
    ]
  }},
  ... (repeat for Core Topics 2-4)
]
Return ONLY the JSON array with no additional commentary.
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
                        "title": str(node.get("title", f"Topic {i + 1}")),
                        "description": str(node.get("description", "")),
                        "content": str(node.get("content", "")),
                        "order": i,
                        "prerequisite_ids": [],  # Start with no prerequisites
                        "children": node.get("children", []),
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
        prompt = f"""You are a curriculum design expert. For the existing roadmap (ID: {roadmap_id}) at skill level {progress_level}, generate content for the next node titled '{current_node}'. Return a pure JSON object with keys: title, description, content, prerequisites (list of existing node titles that should be prerequisites, may be empty). Format as JSON only."""
        messages = [
            {"role": "system", "content": "You are an expert curriculum designer."},
            {"role": "user", "content": prompt},
        ]
        try:
            response = await self._get_completion(messages)
            return {
                "title": str(response.get("title", current_node)),
                "description": str(response.get("description", "")),
                "content": str(response.get("content", "")),
                "prerequisites": response.get("prerequisites", []),
            }
        except Exception as e:
            self._logger.exception("Error generating node content")
            raise NodeCustomizationError from e
