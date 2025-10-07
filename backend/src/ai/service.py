"""Centralized AI Service for all AI operations.

This service acts as the single entry point for all AI-related functionality
in the application, providing a clean interface that hides implementation details.
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select

from src.ai.client import LLMClient
from src.ai.models import CourseStructure, ExecutionPlan
from src.ai.prompts import (
    ASSISTANT_CHAT_SYSTEM_PROMPT,
)
from src.ai.rag.embeddings import VectorRAG
from src.ai.rag.service import RAGService
from src.books.models import Book
from src.database.session import async_session_maker
from src.videos.models import Video


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

    # Code execution operations
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
        """Generate a sandbox execution plan for code execution."""
        return await self._llm_client.generate_execution_plan(
            language=language,
            source_code=source_code,
            stderr=stderr,
            stdin=stdin,
            sandbox_state=sandbox_state,
            user_id=user_id,
        )

    # RAG helpers
    async def get_book_rag_context(self, book_id: UUID, query: str, user_id: UUID, limit: int = 5) -> list[dict]:
        """Search book chunks via VectorRAG.search with ownership enforcement.

        Returns a list of result dicts with content and metadata (e.g., page).
        """
        async with async_session_maker() as session:
            # Ownership check
            book = await session.scalar(select(Book).where(Book.id == book_id, Book.user_id == user_id))
            if not book:
                return []

            rag = VectorRAG()
            results = await rag.search(session, doc_type="book", query=query, limit=limit, doc_id=book.id)
            return [r.model_dump() for r in results]

    async def get_video_rag_context(self, video_id: UUID, query: str, user_id: UUID, limit: int = 5) -> list[dict]:
        """Search video transcript chunks via VectorRAG.search with ownership enforcement.

        Returns a list of result dicts with content and metadata (e.g., start/end).
        """
        async with async_session_maker() as session:
            # Ownership check
            video = await session.scalar(select(Video).where(Video.id == video_id, Video.user_id == user_id))
            if not video:
                return []

            rag = VectorRAG()
            results = await rag.search(session, doc_type="video", query=query, limit=limit, doc_id=video.id)
            return [r.model_dump() for r in results]


# Singleton instance
_ai_service: AIService | None = None


def get_ai_service() -> AIService:
    """Get the singleton AI service instance."""
    global _ai_service  # noqa: PLW0603
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service
