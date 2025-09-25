"""Centralized AI Service for all AI operations.

This service acts as the single entry point for all AI-related functionality
in the application, providing a clean interface that hides implementation details.
"""

import logging
from typing import Any
from uuid import UUID

from src.ai.client import LLMClient
from src.ai.models import CourseStructure
from src.ai.prompts import (
    ASSISTANT_CHAT_SYSTEM_PROMPT,
)
from src.ai.rag.service import RAGService


logger = logging.getLogger(__name__)


class AIService:
    """ALL AI operations go through here."""

    def __init__(self) -> None:
        self._rag_service = RAGService()
        self._llm_client = LLMClient(rag_service=self._rag_service)

    # Course operations
    async def course_generate(
        self,
        user_id: UUID,
        topic: str,
        description: str = "",
        **_kwargs: Any,  # Accept additional kwargs like content_type
    ) -> CourseStructure:
        """Generate a course roadmap."""
        # Build prompt with topic and description
        user_prompt = topic
        if description:
            user_prompt += f"\n\nAdditional details: {description}"

        return await self._llm_client.generate_course_structure(
            user_prompt=user_prompt,
            user_id=str(user_id)
        )

    # General operations
    async def assistant_chat(
        self,
        user_id: UUID,
        message: str,
        context: dict | None = None,
        history: list[dict] | None = None,
        **_kwargs: Any,
    ) -> str:
        """General assistant chat with optional context."""
        # Build messages
        messages = [{"role": "system", "content": ASSISTANT_CHAT_SYSTEM_PROMPT}]

        if history:
            messages.extend(history)

        if context:
            # Add any additional context messages if needed
            if "messages" in context:
                # Use the provided messages instead of building our own
                messages = context["messages"]
            else:
                # Add context as text to the user message
                context_str = f"\n\nCurrent context: {context}"
                message += context_str

        messages.append({"role": "user", "content": message})

        # Use completion with user context
        response = await self._llm_client.get_completion(
            messages=messages,
            user_id=str(user_id),
            format_json=False
        )

        return str(response)


# Singleton instance
_ai_service: AIService | None = None


def get_ai_service() -> AIService:
    """Get the singleton AI service instance."""
    global _ai_service  # noqa: PLW0603
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service
