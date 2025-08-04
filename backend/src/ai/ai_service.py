"""Centralized AI Service for all AI operations.

This service acts as the single entry point for all AI-related functionality
in the application, providing a clean interface that hides implementation details.
"""

import logging
from typing import Any
from uuid import UUID

from src.ai.client import ModelManager
from src.ai.prompts import (
    ASSISTANT_CHAT_SYSTEM_PROMPT,
)
from src.ai.rag.service import RAGService
from src.core.exceptions import DomainError
from src.database.session import async_session_maker


logger = logging.getLogger(__name__)


class AIServiceError(DomainError):
    """Base exception for AI service errors."""


class AIService:
    """ALL AI operations go through here."""

    def __init__(self) -> None:
        self._model_manager = ModelManager()
        self._rag_service = RAGService()

    async def process_content(self, content_type: str, action: str, user_id: UUID, **kwargs: Any) -> Any:
        """Route AI requests to appropriate handlers.

        Args:
            content_type: Type of content (book, video, course, flashcard, etc.)
            action: Action to perform (question, summarize, generate, etc.)
            user_id: User ID for the request
            **kwargs: Additional parameters specific to the action

        Returns
        -------
            Response from the AI operation

        Raises
        ------
            AIServiceError: If the content_type/action combination is not supported
        """
        # Simple routing table
        handler = {
            # Book operations
            ("book", "question"): self._book_question,
            ("book", "summarize"): self._book_summary,
            ("book", "extract"): self._book_extract,
            ("book", "chat"): self._book_chat,
            ("book", "process_rag"): self._book_process_rag,
            # Video operations
            ("video", "transcript"): self._video_transcript,
            ("video", "summarize"): self._video_summary,
            ("video", "question"): self._video_question,
            ("video", "chat"): self._video_chat,
            ("video", "process_rag"): self._video_process_rag,
            # Course operations
            ("course", "generate"): self._course_generate,
            ("course", "lesson"): self._course_lesson,
            ("course", "update"): self._course_update,
            ("course", "chat"): self._course_chat,
            # Flashcard operations
            ("flashcard", "generate"): self._flashcard_generate,
            ("flashcard", "hint"): self._flashcard_hint,
            ("flashcard", "explain"): self._flashcard_explain,
            # Tagging operations (all content types use the same handler)
            ("book", "tag"): self._content_tag,
            ("video", "tag"): self._content_tag,
            ("course", "tag"): self._content_tag,
            ("flashcard", "tag"): self._content_tag,
            ("content", "tag"): self._content_tag,  # Keep for backward compatibility
            # General operations
            ("assistant", "chat"): self._assistant_chat,
        }.get((content_type, action))

        if not handler:
            error_msg = f"Unknown operation: {content_type}/{action}"
            raise AIServiceError(error_msg)

        # Special handling for _content_tag which requires content_type as keyword argument
        if handler == self._content_tag:
            return await handler(user_id, content_type=content_type, **kwargs)

        # Call the handler with all kwargs
        return await handler(user_id, **kwargs)

    # Book operations
    async def _book_question(
        self, user_id: UUID, book_id: str, question: str, _page: int | None = None, **_kwargs: Any
    ) -> str:
        """Answer a question about a book."""
        logger.info("Processing book question for user %s: %s", user_id, question[:50])

        # Get RAG context if available
        context = ""
        if book_id:
            async with async_session_maker() as session:
                search_results = await self._rag_service.search_documents(
                    session=session,
                    roadmap_id=UUID(book_id),  # Using roadmap_id for now
                    query=question,
                    top_k=5,
                )

                if search_results:
                    context_parts = [f"[Page {r.chunk_number}] {r.chunk_content}" for r in search_results]
                    context = "\n\n".join(context_parts)

        # Prepare messages
        messages = [
            {
                "role": "system",
                "content": "You are an expert at answering questions about books. Use the provided context to give accurate answers.",
            },
            {"role": "user", "content": f"Context from the book:\n{context}\n\nQuestion: {question}"},
        ]

        # Get response
        response = await self._model_manager.get_completion_with_memory(
            messages=messages, user_id=user_id, format_json=False
        )

        return str(response)

    async def _book_summary(
        self, user_id: UUID, _book_id: str, _page_range: tuple[int, int] | None = None, **_kwargs: Any
    ) -> str:
        """Generate a summary of a book or specific pages."""
        logger.info("Generating book summary for user %s", user_id)

        # TODO: Implement book summarization with RAG
        messages = [
            {"role": "system", "content": "You are an expert at summarizing educational content."},
            {"role": "user", "content": "Please summarize the key points from this book section."},
        ]

        response = await self._model_manager.get_completion_with_memory(
            messages=messages, user_id=user_id, format_json=False
        )

        return str(response)

    async def _book_extract(self, user_id: UUID, _book_id: str, extract_type: str, **_kwargs: Any) -> list[dict]:
        """Extract specific information from a book (e.g., key concepts, exercises)."""
        logger.info("Extracting %s from book for user %s", extract_type, user_id)

        # TODO: Implement extraction logic
        return []

    async def _book_chat(
        self, user_id: UUID, _book_id: str, message: str, history: list[dict] | None = None, **_kwargs: Any
    ) -> str:
        """Chat about a book with context."""
        logger.info("Book chat for user %s", user_id)

        # Build conversation with book context
        messages = history or []
        messages.append({"role": "user", "content": message})

        response = await self._model_manager.get_completion_with_memory(
            messages=messages, user_id=user_id, format_json=False
        )

        return str(response)

    async def _book_process_rag(self, _user_id: UUID, book_id: str, _file_path: str, **_kwargs: Any) -> dict:
        """Process a book for RAG indexing."""
        logger.info("Processing book %s for RAG", book_id)

        # This would be called by the background processor
        # Returns status of the processing
        return {"status": "processing", "book_id": book_id}

    # Video operations
    async def _video_transcript(self, _user_id: UUID, video_id: str, _url: str, **_kwargs: Any) -> str:
        """Get or generate transcript for a video."""
        logger.info("Getting transcript for video %s", video_id)

        # TODO: Implement transcript fetching/generation
        return "Transcript would be fetched here"

    async def _video_summary(self, user_id: UUID, _video_id: str, transcript: str, **_kwargs: Any) -> str:
        """Summarize a video based on its transcript."""
        logger.info("Summarizing video for user %s", user_id)

        messages = [
            {
                "role": "system",
                "content": "You are an expert at summarizing educational videos. Create clear, structured summaries.",
            },
            {"role": "user", "content": f"Please summarize this video transcript:\n\n{transcript[:3000]}"},
        ]

        response = await self._model_manager.get_completion_with_memory(
            messages=messages, user_id=user_id, format_json=False
        )

        return str(response)

    async def _video_question(
        self, user_id: UUID, _video_id: str, question: str, _timestamp: float | None = None, **_kwargs: Any
    ) -> str:
        """Answer a question about a video."""
        logger.info("Answering video question for user %s", user_id)

        # TODO: Get context from video transcript/RAG
        messages = [
            {"role": "system", "content": "You are an expert at answering questions about educational videos."},
            {"role": "user", "content": question},
        ]

        response = await self._model_manager.get_completion_with_memory(
            messages=messages, user_id=user_id, format_json=False
        )

        return str(response)

    async def _video_chat(
        self, user_id: UUID, video_id: str, message: str, history: list[dict] | None = None, **_kwargs: Any
    ) -> str:
        """Chat about a video with context."""
        return await self._book_chat(user_id, video_id, message, history)

    async def _video_process_rag(self, _user_id: UUID, video_id: str, _transcript: str, **_kwargs: Any) -> dict:
        """Process a video transcript for RAG indexing."""
        logger.info("Processing video %s for RAG", video_id)

        return {"status": "processing", "video_id": video_id}

    # Course operations
    async def _course_generate(
        self,
        user_id: UUID,
        topic: str,
        skill_level: str,
        description: str = "",
        use_tools: bool = False,
        **_kwargs: Any,  # Accept additional kwargs like content_type
    ) -> dict:
        """Generate a course roadmap."""
        logger.info("Generating course for user %s: %s", user_id, topic)

        # Use the existing roadmap generation logic
        roadmap = await self._model_manager.generate_roadmap_content(
            user_prompt=topic, skill_level=skill_level, description=description, use_tools=use_tools
        )

        return roadmap  # noqa: RET504

    async def _course_lesson(
        self, user_id: UUID, course_id: str, lesson_meta: dict[str, Any], **_kwargs: Any
    ) -> tuple[str, list[dict]]:
        """Generate a lesson for a course."""
        logger.info("Generating lesson for course %s", course_id)

        # Import create_lesson_body here to avoid circular imports
        from src.ai.client import create_lesson_body

        # Add user_id to lesson meta for personalization
        lesson_meta["user_id"] = user_id

        return await create_lesson_body(lesson_meta)

    async def _course_update(self, user_id: UUID, course_id: str, _updates: dict, **_kwargs: Any) -> dict:
        """Update course content based on feedback."""
        logger.info("Updating course %s for user %s", course_id, user_id)

        # TODO: Implement course update logic
        return {"status": "updated", "course_id": course_id}

    async def _course_chat(
        self, user_id: UUID, course_id: str, message: str, history: list[dict] | None = None, **_kwargs: Any
    ) -> str:
        """Chat about a course with context."""
        return await self._book_chat(user_id, course_id, message, history)

    # Flashcard operations
    async def _flashcard_generate(self, user_id: UUID, content: str, count: int = 10, **_kwargs: Any) -> list[dict]:
        """Generate flashcards from content."""
        logger.info("Generating %d flashcards for user %s", count, user_id)

        messages = [
            {
                "role": "system",
                "content": f"Generate {count} flashcards from the provided content. Return as JSON array with 'front' and 'back' fields.",
            },
            {"role": "user", "content": f"Create flashcards from this content:\n\n{content[:2000]}"},
        ]

        response = await self._model_manager.get_completion_with_memory(
            messages=messages, user_id=user_id, format_json=True
        )

        return response if isinstance(response, list) else []

    async def _flashcard_hint(self, user_id: UUID, _card_id: str, front: str, back: str, **_kwargs: Any) -> str:
        """Generate a hint for a flashcard."""
        logger.info("Generating hint for flashcard %s", _card_id)

        messages = [
            {"role": "system", "content": "Generate a helpful hint for this flashcard without giving away the answer."},
            {"role": "user", "content": f"Front: {front}\nBack: {back}\n\nGenerate a hint:"},
        ]

        response = await self._model_manager.get_completion_with_memory(
            messages=messages, user_id=user_id, format_json=False
        )

        return str(response)

    async def _flashcard_explain(self, user_id: UUID, _card_id: str, front: str, back: str, **_kwargs: Any) -> str:
        """Explain a flashcard concept in detail."""
        logger.info("Explaining flashcard %s", _card_id)

        messages = [
            {"role": "system", "content": "Explain this flashcard concept in detail with examples."},
            {"role": "user", "content": f"Front: {front}\nBack: {back}\n\nExplain this concept:"},
        ]

        response = await self._model_manager.get_completion_with_memory(
            messages=messages, user_id=user_id, format_json=False
        )

        return str(response)

    # General operations
    async def _content_tag(self, _user_id: UUID, *, content_type: str, title: str, preview: str) -> list[dict]:
        """Generate tags for any content type."""
        logger.info("Generating tags for %s content", content_type)

        return await self._model_manager.generate_content_tags(
            content_type=content_type, title=title, content_preview=preview
        )

    async def _assistant_chat(
        self,
        user_id: UUID,
        message: str,
        context: dict | None = None,
        history: list[dict] | None = None,
        **_kwargs: Any,
    ) -> str:
        """General assistant chat with optional context."""
        logger.info("Assistant chat for user %s", user_id)

        # Build messages
        messages = [{"role": "system", "content": ASSISTANT_CHAT_SYSTEM_PROMPT}]

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": message})

        # Add context if provided
        if context:
            context_str = f"\n\nCurrent context: {context}"
            messages[-1]["content"] += context_str

        response = await self._model_manager.get_completion_with_memory(
            messages=messages, user_id=user_id, format_json=False
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
