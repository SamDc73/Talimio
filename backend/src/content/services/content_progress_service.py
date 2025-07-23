"""Content progress service."""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)


class ContentProgressService:
    """Service for unified content operations including progress tracking."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the content service."""
        self.session = session


    def _convert_to_uuid(self, content_id: str | UUID) -> UUID | None:
        """Convert string to UUID if needed."""
        if isinstance(content_id, UUID):
            return content_id
        try:
            return UUID(content_id)
        except ValueError:
            return None

    async def _get_course_progress(self, content_id: UUID, user_id: UUID | None) -> int:
        """Get course progress."""
        from src.courses.services.course_progress_service import CourseProgressService
        if user_id is None:
            return 0
        try:
            user_uuid = UUID(user_id)
            service = CourseProgressService(self.session, user_id)
            return await service.get_course_progress_percentage(content_id, user_uuid)
        except ValueError:
            return 0

    async def _get_book_progress(self, content_id: UUID, _user_id: UUID | None) -> int:
        """Get book progress."""
        from src.books.services.book_service import BookService
        service = BookService(self.session)
        return await service.get_book_progress(content_id)

    async def _get_video_progress(self, content_id: UUID, _user_id: UUID | None) -> int:
        """Get video progress."""
        from src.videos.service import VideoService
        service = VideoService()
        return await service.get_video_progress(content_id)

    async def _get_flashcard_progress(self, _content_id: UUID, _user_id: UUID | None) -> int:
        """Get flashcard progress."""
        return 0  # TODO: Implement when flashcard progress is needed


    def _group_items_by_type(self, items: list[tuple[str, str | UUID]]) -> dict[str, list[str | UUID]]:
        """Group items by content type."""
        grouped = {}
        for content_type, content_id in items:
            if content_type not in grouped:
                grouped[content_type] = []
            grouped[content_type].append(content_id)
        return grouped

    async def _process_courses(self, course_ids: list[str | UUID], user_id: UUID | None) -> dict[str, int]:
        """Process course progress for bulk operation."""
        if not course_ids or not user_id:
            return {f"course:{course_id}": 0 for course_id in course_ids}

        from src.courses.services.course_progress_service import CourseProgressService
        try:
            user_uuid = UUID(user_id)
            service = CourseProgressService(self.session, user_id)
            results = {}
            for course_id in course_ids:
                try:
                    course_uuid = self._convert_to_uuid(course_id)
                    if course_uuid:
                        progress = await service.get_course_progress_percentage(course_uuid, user_uuid)
                        results[f"course:{course_id}"] = progress
                    else:
                        results[f"course:{course_id}"] = 0
                except Exception:
                    results[f"course:{course_id}"] = 0
            return results
        except ValueError:
            return {f"course:{course_id}": 0 for course_id in course_ids}

    async def _process_videos(self, video_ids: list[str | UUID]) -> dict[str, int]:
        """Process video progress for bulk operation."""
        if not video_ids:
            return {}

        from src.videos.service import VideoService
        service = VideoService()
        results = {}
        for video_id in video_ids:
            try:
                video_uuid = self._convert_to_uuid(video_id)
                if video_uuid:
                    progress = await service.get_video_progress(video_uuid)
                    results[f"youtube:{video_id}"] = progress
                else:
                    results[f"youtube:{video_id}"] = 0
            except Exception:
                results[f"youtube:{video_id}"] = 0
        return results

    async def _process_books(self, book_ids: list[str | UUID]) -> dict[str, int]:
        """Process book progress for bulk operation."""
        if not book_ids:
            return {}

        from src.books.services.book_service import BookService
        service = BookService(self.session)
        results = {}
        for book_id in book_ids:
            try:
                book_uuid = self._convert_to_uuid(book_id)
                if book_uuid:
                    progress = await service.get_book_progress(book_uuid)
                    results[f"book:{book_id}"] = progress
                else:
                    results[f"book:{book_id}"] = 0
            except Exception:
                results[f"book:{book_id}"] = 0
        return results


async def _calculate_course_progress(session: AsyncSession, items: list[Any], user_id: str) -> list[Any]:
    """Calculate accurate course progress using CourseProgressService (DRY)."""
    from src.courses.services.course_progress_service import CourseProgressService

    # Filter for course items only (roadmap type in DB, but shows as course in enum)
    course_items = [item for item in items if hasattr(item, "type") and str(item.type) in ("roadmap", "course", "ContentType.COURSE")]

    if not course_items:
        return items

    # Initialize progress service
    progress_service = CourseProgressService(session, user_id)

    # Calculate progress for each course using our DRY service
    for item in course_items:
        try:
            course_id = UUID(item.id)
            user_uuid = UUID(user_id)

            # Use our DRY CourseProgressService
            progress = await progress_service.get_course_progress_percentage(course_id, user_uuid)
            stats = await progress_service.get_lesson_completion_stats(course_id, user_uuid)

            # Update the item's progress
            item.progress = float(progress)
            if hasattr(item, "completed_lessons"):
                item.completed_lessons = stats["completed_lessons"]

        except (ValueError, Exception) as e:
            # Keep original progress (0) if there's an error
            logger.debug(f"Error calculating course progress for {item.id}: {e}")

    return items


async def _calculate_book_progress(session: AsyncSession, items: list[Any], user_id: str) -> list[Any]:
    """Calculate accurate book progress using BookProgressService (matching course pattern)."""
    from src.books.services.book_progress_service import BookProgressService

    # Filter for book items only
    book_items = [item for item in items if hasattr(item, "type") and str(item.type) == "book"]

    if not book_items:
        return items

    # Initialize progress service
    progress_service = BookProgressService(session, user_id)

    # Calculate progress for each book using TOC-based progress
    for item in book_items:
        try:
            book_id = UUID(item.id)

            # Use our BookProgressService for TOC-based progress
            progress = await progress_service.get_book_toc_progress_percentage(book_id, user_id)
            stats = await progress_service.get_toc_completion_stats(book_id, user_id)

            # Update the item's progress with TOC-based calculation
            item.progress = float(progress)

            # Store additional stats for web app if needed
            if hasattr(item, "completed_sections"):
                item.completed_sections = stats["completed_sections"]
            if hasattr(item, "total_sections"):
                item.total_sections = stats["total_sections"]

        except (ValueError, Exception) as e:
            # Keep original progress (page-based) if there's an error
            logger.debug(f"Error calculating TOC progress for book {item.id}: {e}")

    return items
