import logging
import os
from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from litellm import acompletion
from src.config.settings import get_settings
from src.utils.validators import validate_uuid


def _raise_roadmap_error() -> None:
    """Raise HTTP exception for roadmap generation failure."""
    raise HTTPException(status_code=500, detail="Failed to generate roadmap content")


def _raise_node_error() -> None:
    """Raise HTTP exception for node customization failure."""
    raise HTTPException(status_code=500, detail="Failed to customize node content")


def _raise_exercise_error() -> None:
    """Raise HTTP exception for exercise generation failure."""
    raise HTTPException(status_code=500, detail="Failed to generate exercises")


class ModelManager:
    """Manage AI model interactions for the learning roadmap platform using LiteLLM."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            msg = "OPENAI_API_KEY not found in environment variables"
            raise ValueError(msg)

        os.environ["OPENAI_API_KEY"] = self.api_key
        self.model = "gpt-4o"
        self._logger = logging.getLogger(__name__)

    async def _get_completion(
        self,
        messages: Sequence[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str | None:
        """Get completion from LiteLLM."""
        try:
            response = await acompletion(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception:
            self._logger.exception("Error getting completion from LiteLLM")
            return None

    async def generate_roadmap_content(
        self,
        title: str,
        skill_level: str,
        description: str,
    ) -> dict:
        """Generate initial roadmap content structure."""
        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are an expert curriculum designer helping create learning roadmaps.",
                },
                {
                    "role": "user",
                    "content": f"""Create a learning roadmap for:
                    Title: {title}
                    Skill Level: {skill_level}
                    Description: {description}

                    Generate a structured learning path with key topics and prerequisites.""",
                },
            ]

            content = await self._get_completion(messages)
            if not content:
                _raise_roadmap_error()

            return {
                "content": content,
                "created_at": datetime.now(tz=timezone.utc),
            }

        except Exception as err:
            self._logger.exception("Error generating roadmap content")
            raise HTTPException(
                status_code=500,
                detail="Failed to generate roadmap content",
            ) from err

    async def customize_node_content(
        self,
        node_id: UUID,
        user_skill_level: str,
        content: str,
    ) -> str:
        """Customize node content based on user's skill level."""
        if not validate_uuid(node_id):
            msg = "Invalid node ID"
            raise ValueError(msg)

        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are an expert tutor adapting content to different skill levels.",
                },
                {
                    "role": "user",
                    "content": f"""Customize this content for a {user_skill_level} level learner:

                    {content}

                    Adjust the depth and complexity accordingly while maintaining the core concepts.""",
                },
            ]

            customized_content = await self._get_completion(messages)
            if not customized_content:
                _raise_node_error()
            else:
                return customized_content

        except Exception as err:
            self._logger.exception("Error customizing node content")
            raise HTTPException(
                status_code=500,
                detail="Failed to customize node content",
            ) from err

    async def generate_practice_exercises(
        self,
        node_id: UUID,
        topic: str,
        difficulty: str,
    ) -> list[dict]:
        """Generate practice exercises for a node."""
        if not validate_uuid(node_id):
            msg = "Invalid node ID"
            raise ValueError(msg)

        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are an expert at creating educational exercises.",
                },
                {
                    "role": "user",
                    "content": f"""Create 3 practice exercises for:
                    Topic: {topic}
                    Difficulty: {difficulty}

                    Include problem statement and solution for each exercise.
                    Format each exercise as:

                    Exercise 1:
                    [Problem]

                    Solution:
                    [Solution]

                    (and so on for exercises 2 and 3)""",
                },
            ]

            content = await self._get_completion(messages)
            if not content:
                _raise_exercise_error()
            else:
                return self._parse_exercises(content)

        except Exception as err:
            self._logger.exception("Error generating exercises")
            raise HTTPException(
                status_code=500,
                detail="Failed to generate exercises",
            ) from err

    def _parse_exercises(self, content: str) -> list[dict]:
        """Parse exercise content into structured format."""
        exercises = []
        current_exercise: dict[str, str] = {}

        for original_line in content.split("\n"):
            cleaned_line = original_line.strip()
            if cleaned_line.startswith("Exercise"):
                if current_exercise:
                    exercises.append(current_exercise)
                current_exercise = {"problem": ""}
            elif cleaned_line.startswith("Solution"):
                current_exercise["solution"] = ""
            elif "problem" in current_exercise:
                if "solution" not in current_exercise:
                    current_exercise["problem"] += cleaned_line + "\n"
                else:
                    current_exercise["solution"] += cleaned_line + "\n"

        if current_exercise:
            exercises.append(current_exercise)

        return [
            {
                "problem": ex["problem"].strip(),
                "solution": ex["solution"].strip(),
            }
            for ex in exercises
        ]
