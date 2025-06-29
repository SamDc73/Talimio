"""Context retrieval strategies for the assistant."""

import logging
from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

import pymupdf as fitz
from pydantic import BaseModel

from src.books.service import get_book
from src.courses.services.course_service import CourseService
from src.database.session import async_session_maker
from src.videos.service import VideoService


class ContextData(BaseModel):
    """Container for extracted context data."""

    content: str  # The extracted context text
    source: str  # Source description (e.g., "PDF page 5", "Video 02:15-03:45")
    metadata: dict[str, Any] = {}  # Additional metadata about the context


class ContextRetriever(ABC):
    """Base interface for context retrieval strategies."""

    @abstractmethod
    async def retrieve_context(
        self, resource_id: UUID, context_meta: dict[str, Any] | None = None
    ) -> ContextData | None:
        """
        Retrieve context for a specific resource.

        Args:
            resource_id: UUID of the resource (book, video, course)
            context_meta: Position or metadata information (page, timestamp, lesson_id, etc.)

        Returns
        -------
            ContextData containing the extracted context, or None if no context available
        """


class BookContextStrategy(ContextRetriever):
    """Context retrieval strategy for PDF books."""

    async def retrieve_context(
        self, resource_id: UUID, context_meta: dict[str, Any] | None = None
    ) -> ContextData | None:
        """
        Extract text from current page +/- 2 pages for context window.

        Args:
            resource_id: UUID of the book
            context_meta: Should contain 'page' key with current page number

        Returns
        -------
            ContextData with extracted PDF text or None if extraction fails
        """
        try:
            if not context_meta or "page" not in context_meta:
                logging.warning(f"No page information provided for book context retrieval: {resource_id}")
                return None

            current_page = context_meta["page"]

            book = await get_book(resource_id)

            if not book or not book.file_path:
                logging.warning(f"Book not found or no file path: {resource_id}")
                return None

            # Open PDF and extract text from current page +/- 2 pages
            doc = fitz.open(book.file_path)

            # Calculate page range (current page +/- 2, within document bounds)
            start_page = max(0, current_page - 2)
            end_page = min(doc.page_count - 1, current_page + 2)

            extracted_text = []
            for page_num in range(start_page, end_page + 1):
                page = doc.load_page(page_num)
                page_text = page.get_text()

                # Include page headers for better context
                if page_text.strip():
                    header = f"--- Page {page_num + 1} ---"
                    if page_num == current_page:
                        header += " [CURRENT PAGE]"
                    extracted_text.append(f"{header}\n{page_text}")

            doc.close()

            if not extracted_text:
                return None

            content = "\n\n".join(extracted_text)
            source = f"PDF pages {start_page + 1}-{end_page + 1} (current: {current_page + 1})"

            return ContextData(
                content=content,
                source=source,
                metadata={
                    "book_id": str(resource_id),
                    "book_title": book.title,
                    "current_page": current_page,
                    "page_range": [start_page, end_page],
                    "total_pages": doc.page_count,
                },
            )

        except Exception as e:
            logging.exception(f"Failed to retrieve book context for {resource_id}: {e}")
            return None


class VideoContextStrategy(ContextRetriever):
    """Context retrieval strategy for video transcripts."""

    async def retrieve_context(  # noqa: C901
        self, resource_id: UUID, context_meta: dict[str, Any] | None = None
    ) -> ContextData | None:
        """
        Extract transcript around current timestamp (+/- 60 seconds).

        Args:
            resource_id: UUID of the video
            context_meta: Should contain 'timestamp' key with current timestamp in seconds

        Returns
        -------
            ContextData with extracted transcript text or None if extraction fails
        """
        try:
            if not context_meta or "timestamp" not in context_meta:
                logging.warning(f"No timestamp information provided for video context retrieval: {resource_id}")
                return None

            current_timestamp = context_meta["timestamp"]
            context_window = 60  # seconds

            async with async_session_maker() as session:
                video_service = VideoService()
                video = await video_service.get_video(session, str(resource_id))

                if not video:
                    logging.warning(f"Video not found: {resource_id}")
                    return None

                # Get transcript segments around the current timestamp
                if not hasattr(video, "transcript_segments") or not video.transcript_segments:
                    logging.warning(f"No transcript available for video: {resource_id}")
                    return None

                # Filter transcript segments within the time window
                start_time = max(0, current_timestamp - context_window)
                end_time = current_timestamp + context_window

                relevant_segments = []
                for segment in video.transcript_segments:
                    if "start" in segment and "text" in segment:
                        segment_start = segment["start"]
                        segment_end = segment.get("end", segment_start + 1)

                        # Include segment if it overlaps with our time window
                        if segment_start <= end_time and segment_end >= start_time:
                            relevant_segments.append(segment)

                if not relevant_segments:
                    return None

                # Format transcript with timestamps
                transcript_parts = []
                for segment in relevant_segments:
                    timestamp_str = f"[{segment['start']:.1f}s]"
                    if segment["start"] <= current_timestamp <= segment.get("end", segment["start"] + 1):
                        timestamp_str += " [CURRENT]"
                    transcript_parts.append(f"{timestamp_str} {segment['text']}")

                content = "\n".join(transcript_parts)
                source = f"Video transcript {start_time:.1f}s-{end_time:.1f}s (current: {current_timestamp:.1f}s)"

                return ContextData(
                    content=content,
                    source=source,
                    metadata={
                        "video_id": str(resource_id),
                        "video_title": video.title,
                        "current_timestamp": current_timestamp,
                        "time_window": [start_time, end_time],
                        "segment_count": len(relevant_segments),
                    },
                )

        except Exception as e:
            logging.exception(f"Failed to retrieve video context for {resource_id}: {e}")
            return None


class CourseContextStrategy(ContextRetriever):
    """Context retrieval strategy for course lessons."""

    async def retrieve_context(  # noqa: C901
        self, resource_id: UUID, context_meta: dict[str, Any] | None = None
    ) -> ContextData | None:
        """
        Fetch current lesson content in real-time.

        Args:
            resource_id: UUID of the course
            context_meta: Should contain 'lesson_id' key with current lesson UUID

        Returns
        -------
            ContextData with current lesson content or None if extraction fails
        """
        try:
            if not context_meta or "lesson_id" not in context_meta:
                logging.warning(f"No lesson_id provided for course context retrieval: {resource_id}")
                return None

            lesson_id = context_meta["lesson_id"]

            async with async_session_maker() as session:
                course_service = CourseService(session)
                course = await course_service.get_course_by_id(resource_id)

                if not course:
                    logging.warning(f"Course not found: {resource_id}")
                    return None

                # Find the specific lesson
                lesson = None
                module_title = ""

                for module in course.modules:
                    for lesson_item in module.lessons:
                        if str(lesson_item.id) == str(lesson_id):
                            lesson = lesson_item
                            module_title = module.title
                            break
                    if lesson:
                        break

                if not lesson:
                    logging.warning(f"Lesson not found in course {resource_id}: {lesson_id}")
                    return None

                # Handle different lesson generation states
                if lesson.status == "pending":
                    content = "[Lesson is being generated...]"
                elif lesson.status == "generating":
                    content = "[Lesson is currently being generated...]"
                elif lesson.status == "complete" and lesson.content:
                    content = lesson.content
                else:
                    content = "[Lesson content not available]"

                source = f"Course lesson: {module_title} > {lesson.title}"

                return ContextData(
                    content=content,
                    source=source,
                    metadata={
                        "course_id": str(resource_id),
                        "course_title": course.title,
                        "lesson_id": str(lesson_id),
                        "lesson_title": lesson.title,
                        "module_title": module_title,
                        "lesson_status": lesson.status,
                        "lesson_order": lesson.order,
                    },
                )

        except Exception as e:
            logging.exception(f"Failed to retrieve course context for {resource_id}: {e}")
            return None


def validate_context_request(context_type: str, context_id: UUID, context_meta: dict[str, Any] | None) -> bool:
    """
    Validate context request parameters.

    Args:
        context_type: Type of context ('book', 'video', 'course')
        context_id: UUID of the resource
        context_meta: Position/metadata information

    Returns
    -------
        True if valid, False otherwise
    """
    if context_type not in ["book", "video", "course"]:
        logging.error(f"Invalid context_type: {context_type}")
        return False

    if not context_id:
        logging.error("context_id is required when context_type is provided")
        return False

    # Validate context_meta based on context_type
    if context_meta:
        if context_type == "book" and "page" not in context_meta:
            logging.warning("context_meta should contain 'page' for book context")
        elif context_type == "video" and "timestamp" not in context_meta:
            logging.warning("context_meta should contain 'timestamp' for video context")
        elif context_type == "course" and "lesson_id" not in context_meta:
            logging.warning("context_meta should contain 'lesson_id' for course context")

    return True


def limit_context_size(context: str, max_tokens: int = 4000) -> str:
    """
    Limit context size for token management.

    Args:
        context: The context text to limit
        max_tokens: Maximum number of tokens (approximate using chars/4)

    Returns
    -------
        Truncated context if too long
    """
    # Rough approximation: 1 token ≈ 4 characters
    max_chars = max_tokens * 4

    if len(context) <= max_chars:
        return context

    # Truncate and add indicator
    truncated = context[: max_chars - 50]  # Leave space for truncation message
    truncated += "\n\n[Context truncated for length...]"

    logging.info(f"Context truncated from {len(context)} to {len(truncated)} characters")
    return truncated


class ContextManager:
    """Manager for context retrieval strategies."""

    def __init__(self) -> None:
        self._strategies = {
            "book": BookContextStrategy(),
            "video": VideoContextStrategy(),
            "course": CourseContextStrategy(),
        }

    async def get_context(
        self, context_type: str, resource_id: UUID, context_meta: dict[str, Any] | None = None, max_tokens: int = 4000
    ) -> ContextData | None:
        """
        Get context using the appropriate strategy with validation and size limiting.

        Args:
            context_type: Type of context ('book', 'video', 'course')
            resource_id: UUID of the resource
            context_meta: Position/metadata information
            max_tokens: Maximum context size in tokens

        Returns
        -------
            ContextData or None if context retrieval fails
        """
        # Validate request
        if not validate_context_request(context_type, resource_id, context_meta):
            return None

        if context_type not in self._strategies:
            logging.error(f"Unknown context type: {context_type}")
            return None

        try:
            strategy = self._strategies[context_type]
            context_data = await strategy.retrieve_context(resource_id, context_meta)

            if context_data:
                # Limit context size for token management
                context_data.content = limit_context_size(context_data.content, max_tokens)

                # Log context usage for debugging
                logging.info(
                    f"Retrieved context: type={context_type}, resource={resource_id}, "
                    f"size={len(context_data.content)} chars, source={context_data.source}"
                )

            return context_data

        except Exception:
            logging.exception(f"Error retrieving context: type={context_type}, resource={resource_id}")
            return None
