"""Context retrieval strategies for the assistant."""

import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pymupdf as fitz
from pydantic import BaseModel

from src.books.service import get_book
from src.courses.services.course_service import CourseService
from src.database.session import async_session_maker
from src.storage.lesson_dao import LessonDAO
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

    async def retrieve_context(
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
    """Enhanced context retrieval strategy for course lessons with hierarchical context and progress tracking."""

    async def retrieve_context(  # noqa: PLR0915, PLR0912
        self, resource_id: UUID, context_meta: dict[str, Any] | None = None
    ) -> ContextData | None:
        """
        Fetch hierarchical course content with real-time aggregation and progress tracking.

        Args:
            resource_id: UUID of the course
            context_meta: Can contain 'lesson_id', 'module_id', 'include_hierarchy', 'include_progress'

        Returns
        -------
            ContextData with aggregated course content including hierarchical context
        """
        try:
            if not context_meta:
                context_meta = {}

            lesson_id = context_meta.get("lesson_id")
            module_id = context_meta.get("module_id")
            include_hierarchy = context_meta.get("include_hierarchy", True)
            include_progress = context_meta.get("include_progress", True)
            user_id = context_meta.get("user_id")

            async with async_session_maker() as session:
                course_service = CourseService(session, user_id)
                course = await course_service.get_course(resource_id, user_id)

                if not course:
                    logging.warning(f"Course not found: {resource_id}")
                    return None

                content_parts = []
                metadata = {
                    "course_id": str(resource_id),
                    "course_title": course.title,
                    "course_description": course.description,
                    "skill_level": course.skill_level,
                    "rag_enabled": course.rag_enabled,
                }

                # Course overview context
                content_parts.append(f"=== COURSE: {course.title} ===")
                content_parts.append(f"Description: {course.description}")
                content_parts.append(f"Skill Level: {course.skill_level}")
                content_parts.append("")

                # Get lesson progress data if available
                progress_data = {}
                if include_progress and user_id:
                    try:
                        progress_response = await course_service.get_course_progress(str(resource_id))
                        if progress_response and hasattr(progress_response, "lessons"):
                            for lesson_progress in progress_response.lessons:
                                progress_data[lesson_progress.lesson_id] = lesson_progress.status
                    except Exception as e:
                        logging.warning(f"Could not fetch progress data: {e}")

                # Find target lesson and module
                target_lesson = None
                target_module = None
                current_module_lessons = []

                # Build hierarchical context
                for module in course.modules if hasattr(course, "modules") else course.nodes:
                    module_lessons = []

                    # Get lessons for this module
                    if hasattr(module, "lessons"):
                        module_lessons = module.lessons
                    else:
                        # If using nodes structure, get lessons from lesson DAO
                        lesson_dao = LessonDAO(session)
                        try:
                            lessons_response = await lesson_dao.get_lessons_by_roadmap_id(str(resource_id))
                            if lessons_response and hasattr(lessons_response, "lessons"):
                                # Filter lessons that belong to this module (simplified approach)
                                module_lessons = [
                                    lesson
                                    for lesson in lessons_response.lessons
                                    if lesson.order >= module.order * 10 and lesson.order < (module.order + 1) * 10
                                ]
                        except Exception as e:
                            logging.warning(f"Could not fetch lessons for module {module.id}: {e}")
                            module_lessons = []

                    # Check if target lesson is in this module
                    for lesson in module_lessons:
                        if lesson_id and str(lesson.id) == str(lesson_id):
                            target_lesson = lesson
                            target_module = module
                            current_module_lessons = module_lessons
                            break
                        if module_id and str(module.id) == str(module_id):
                            target_module = module
                            current_module_lessons = module_lessons

                    if target_lesson or (module_id and target_module):
                        break

                # If specific lesson requested, focus on that context
                if lesson_id and target_lesson:
                    metadata.update(
                        {
                            "lesson_id": str(target_lesson.id),
                            "lesson_title": target_lesson.title,
                            "lesson_order": target_lesson.order,
                            "module_id": str(target_module.id),
                            "module_title": target_module.title,
                        }
                    )

                    # Current lesson content
                    if hasattr(target_lesson, "status"):
                        lesson_status = target_lesson.status
                        if lesson_status == "pending":
                            lesson_content = "[Lesson is being generated...]"
                        elif lesson_status == "generating":
                            lesson_content = "[Lesson is currently being generated...]"
                        elif (
                            lesson_status == "complete" and hasattr(target_lesson, "content") and target_lesson.content
                        ):
                            lesson_content = target_lesson.content
                        else:
                            lesson_content = "[Lesson content not available]"
                        metadata["lesson_status"] = lesson_status
                    else:
                        lesson_content = getattr(target_lesson, "content", "[Lesson content not available]")

                    content_parts.append(f"=== CURRENT LESSON: {target_lesson.title} ===")
                    content_parts.append(lesson_content)
                    content_parts.append("")

                    # Add hierarchical context if requested
                    if include_hierarchy and target_module:
                        content_parts.append(f"=== MODULE CONTEXT: {target_module.title} ===")
                        if hasattr(target_module, "description") and target_module.description:
                            content_parts.append(f"Module Description: {target_module.description}")

                        # Show lesson sequence in module
                        content_parts.append("\nLessons in this module:")
                        for lesson in sorted(current_module_lessons, key=lambda x: x.order):
                            status_indicator = ""
                            if include_progress and str(lesson.id) in progress_data:
                                status = progress_data[str(lesson.id)]
                                status_indicator = f" [{status.upper()}]"

                            current_indicator = " [CURRENT]" if str(lesson.id) == str(lesson_id) else ""
                            content_parts.append(f"  - {lesson.title}{status_indicator}{current_indicator}")
                        content_parts.append("")

                # If module requested (no specific lesson), show module overview
                elif module_id and target_module:
                    metadata.update(
                        {
                            "module_id": str(target_module.id),
                            "module_title": target_module.title,
                        }
                    )

                    content_parts.append(f"=== MODULE: {target_module.title} ===")
                    if hasattr(target_module, "description") and target_module.description:
                        content_parts.append(f"Description: {target_module.description}")
                    content_parts.append("")

                    # Show all lessons in module
                    content_parts.append("Lessons in this module:")
                    for lesson in sorted(current_module_lessons, key=lambda x: x.order):
                        status_indicator = ""
                        if include_progress and str(lesson.id) in progress_data:
                            status = progress_data[str(lesson.id)]
                            status_indicator = f" [{status.upper()}]"
                        content_parts.append(f"  - {lesson.title}{status_indicator}")
                    content_parts.append("")

                # If no specific lesson/module, show course overview
                else:
                    content_parts.append("=== COURSE STRUCTURE ===")
                    total_modules = len(course.modules if hasattr(course, "modules") else course.nodes)
                    content_parts.append(f"Total Modules: {total_modules}")

                    if include_hierarchy:
                        for i, module in enumerate(course.modules if hasattr(course, "modules") else course.nodes):
                            content_parts.append(f"\nModule {i + 1}: {module.title}")
                            if hasattr(module, "description") and module.description:
                                content_parts.append(f"  Description: {module.description}")

                # Add progress summary if requested
                if include_progress and progress_data:
                    completed_lessons = sum(1 for status in progress_data.values() if status == "completed")
                    total_lessons = len(progress_data)
                    if total_lessons > 0:
                        progress_percent = (completed_lessons / total_lessons) * 100
                        content_parts.append("=== PROGRESS SUMMARY ===")
                        content_parts.append(
                            f"Completed: {completed_lessons}/{total_lessons} lessons ({progress_percent:.1f}%)"
                        )
                        metadata["progress_completed"] = completed_lessons
                        metadata["progress_total"] = total_lessons
                        metadata["progress_percentage"] = progress_percent

                content = "\n".join(content_parts)

                # Determine source description
                if lesson_id and target_lesson:
                    source = f"Course lesson: {target_module.title} > {target_lesson.title}"
                elif module_id and target_module:
                    source = f"Course module: {target_module.title}"
                else:
                    source = f"Course overview: {course.title}"

                return ContextData(
                    content=content,
                    source=source,
                    metadata=metadata,
                )

        except Exception as e:
            logging.exception(f"Failed to retrieve enhanced course context for {resource_id}: {e}")
            return None


def validate_context_request(context_type: str, context_id: UUID, context_meta: dict[str, Any] | None) -> bool:
    """
    Validate context request parameters with enhanced support for dynamic context updates.

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

    # Enhanced validation for context_meta based on context_type
    if context_meta:
        if context_type == "book":
            if "page" not in context_meta:
                logging.warning("context_meta should contain 'page' for book context")
            # Support for dynamic updates
            if context_meta.get("auto_update"):
                logging.info("Dynamic context updates enabled for book")

        elif context_type == "video":
            if "timestamp" not in context_meta:
                logging.warning("context_meta should contain 'timestamp' for video context")
            # Support for real-time timestamp updates
            if context_meta.get("live_update"):
                logging.info("Live timestamp updates enabled for video")

        elif context_type == "course":
            # Course context is more flexible - can work with lesson_id, module_id, or course overview
            if not any(key in context_meta for key in ["lesson_id", "module_id"]):
                logging.info("Course context will provide overview (no specific lesson_id or module_id)")
            # Support for dynamic progress updates
            if context_meta.get("dynamic_updates"):
                logging.info("Dynamic progress updates enabled for course")

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


class DynamicContextManager:
    """Enhanced context manager with support for dynamic updates and context switching."""

    def __init__(self) -> None:
        self._strategies = {
            "book": BookContextStrategy(),
            "video": VideoContextStrategy(),
            "course": CourseContextStrategy(),
        }
        self._context_cache = {}  # Cache for recently retrieved contexts
        self._context_history = {}  # Track context changes over time

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
            logging.debug(f"DynamicContextManager.get_context: context_type={context_type}, resource_id={resource_id}, context_meta={context_meta}")
            strategy = self._strategies[context_type]
            context_data = await strategy.retrieve_context(resource_id, context_meta)

            if context_data:
                # Limit context size for token management
                context_data.content = limit_context_size(context_data.content, max_tokens)

                # Cache context for potential updates
                cache_key = f"{context_type}:{resource_id}"
                self._context_cache[cache_key] = {
                    "data": context_data,
                    "meta": context_meta,
                    "timestamp": datetime.now(UTC),
                }

                # Track context history for pattern analysis
                self._track_context_usage(context_type, resource_id, context_meta)

                # Log context usage for debugging
                logging.info(
                    f"Retrieved context: type={context_type}, resource={resource_id}, "
                    f"size={len(context_data.content)} chars, source={context_data.source}"
                )

            return context_data

        except Exception:
            logging.exception(f"Error retrieving context: type={context_type}, resource={resource_id}")
            return None

    async def update_context(
        self, context_type: str, resource_id: UUID, new_context_meta: dict[str, Any], max_tokens: int = 4000
    ) -> ContextData | None:
        """
        Update context with new metadata (e.g., new page, timestamp, lesson).

        Args:
            context_type: Type of context ('book', 'video', 'course')
            resource_id: UUID of the resource
            new_context_meta: Updated position/metadata information
            max_tokens: Maximum context size in tokens

        Returns
        -------
            Updated ContextData or None if update fails
        """
        cache_key = f"{context_type}:{resource_id}"

        # Check if we have cached context to compare with
        if cache_key in self._context_cache:
            old_meta = self._context_cache[cache_key]["meta"]

            # Detect significant context changes
            if self._is_significant_change(context_type, old_meta, new_context_meta):
                logging.info(f"Significant context change detected for {context_type}:{resource_id}")

                # Track the context switch
                self._track_context_switch(context_type, resource_id, old_meta, new_context_meta)

        # Get updated context
        return await self.get_context(context_type, resource_id, new_context_meta, max_tokens)

    def _is_significant_change(self, context_type: str, old_meta: dict | None, new_meta: dict) -> bool:
        """Determine if a context change is significant enough to track."""
        if not old_meta or not new_meta:
            return True

        if context_type == "book":
            old_page = old_meta.get("page", 0)
            new_page = new_meta.get("page", 0)
            # Consider page changes of 2+ as significant
            return abs(new_page - old_page) >= 2

        if context_type == "video":
            old_timestamp = old_meta.get("timestamp", 0)
            new_timestamp = new_meta.get("timestamp", 0)
            # Consider timestamp changes of 30+ seconds as significant
            return abs(new_timestamp - old_timestamp) >= 30

        if context_type == "course":
            old_lesson = old_meta.get("lesson_id")
            new_lesson = new_meta.get("lesson_id")
            old_module = old_meta.get("module_id")
            new_module = new_meta.get("module_id")
            # Consider lesson or module changes as significant
            return old_lesson != new_lesson or old_module != new_module

        return False

    def _track_context_usage(self, context_type: str, resource_id: UUID, context_meta: dict | None) -> None:
        """Track context usage patterns for analysis."""
        history_key = f"{context_type}:{resource_id}"

        if history_key not in self._context_history:
            self._context_history[history_key] = []

        self._context_history[history_key].append(
            {"timestamp": datetime.now(UTC), "meta": context_meta, "type": "access"}
        )

        # Keep only recent history (last 50 entries)
        self._context_history[history_key] = self._context_history[history_key][-50:]

    def _track_context_switch(
        self, context_type: str, resource_id: UUID, old_meta: dict | None, new_meta: dict
    ) -> None:
        """Track context switches for pattern analysis."""
        history_key = f"{context_type}:{resource_id}"

        if history_key not in self._context_history:
            self._context_history[history_key] = []

        self._context_history[history_key].append(
            {"timestamp": datetime.now(UTC), "old_meta": old_meta, "new_meta": new_meta, "type": "switch"}
        )

    def get_context_patterns(self, context_type: str, resource_id: UUID) -> dict[str, Any]:
        """
        Analyze context usage patterns for a specific resource.

        Returns
        -------
            Dictionary with usage statistics and patterns
        """
        history_key = f"{context_type}:{resource_id}"
        history = self._context_history.get(history_key, [])

        if not history:
            return {"total_accesses": 0, "switches": 0, "patterns": {}}

        total_accesses = len([h for h in history if h["type"] == "access"])
        switches = len([h for h in history if h["type"] == "switch"])

        # Calculate time spent in different contexts
        time_patterns = {}
        for i, entry in enumerate(history):
            if entry["type"] == "switch" and i < len(history) - 1:
                next_entry = history[i + 1]
                duration = (next_entry["timestamp"] - entry["timestamp"]).total_seconds()

                if context_type == "course" and entry["new_meta"]:
                    lesson_id = entry["new_meta"].get("lesson_id", "unknown")
                    time_patterns[lesson_id] = time_patterns.get(lesson_id, 0) + duration

        return {
            "total_accesses": total_accesses,
            "switches": switches,
            "time_patterns": time_patterns,
            "last_access": history[-1]["timestamp"] if history else None,
        }


# Maintain backward compatibility
class ContextManager(DynamicContextManager):
    """Backward compatible context manager that inherits enhanced functionality."""
