"""Centralized progress calculation service.

This module provides a single source of truth for all progress calculations
across different content types (courses, books, videos, flashcards).
"""

from uuid import UUID

from sqlalchemy import String, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.books.models import BookChapter, BookProgress
from src.courses.models import LessonProgress, Node
from src.videos.models import Video, VideoChapter


class ProgressCalculator:
    """Unified progress calculator for all content types."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_course_progress(self, course_id: UUID) -> int:
        """Calculate course progress based on completed lessons.
        
        Returns percentage (0-100) of completed lessons.
        """
        # Count total lessons (nodes with parent_id)
        total_query = select(func.count(Node.id)).where(
            Node.roadmap_id == course_id,
            Node.parent_id.is_not(None)
        )
        total_result = await self.session.execute(total_query)
        total_lessons = total_result.scalar() or 0

        if total_lessons == 0:
            return 0

        # Count completed lessons from Progress table
        completed_query = select(func.count(LessonProgress.id)).select_from(
            LessonProgress
        ).join(
            Node, func.cast(Node.id, String) == LessonProgress.lesson_id
        ).where(
            Node.roadmap_id == course_id,
            LessonProgress.status == "completed"
        )
        completed_result = await self.session.execute(completed_query)
        completed_lessons = completed_result.scalar() or 0

        return int((completed_lessons / total_lessons) * 100)

    async def get_video_progress(self, video_id: UUID) -> int:
        """Calculate video progress based on completed chapters.
        
        Returns percentage (0-100) of completed chapters.
        """
        # Count total and completed chapters
        stats_query = select(
            func.count(VideoChapter.id).label("total"),
            func.count(VideoChapter.id).filter(VideoChapter.status == "done").label("completed")
        ).where(VideoChapter.video_uuid == video_id)

        result = await self.session.execute(stats_query)
        stats = result.first()

        if not stats or stats.total == 0:
            # Fall back to video completion_percentage if no chapters
            video_query = select(Video.completion_percentage).where(Video.uuid == video_id)
            video_result = await self.session.execute(video_query)
            completion = video_result.scalar()
            return int(completion or 0)

        return int((stats.completed / stats.total) * 100)

    async def get_book_progress(self, book_id: UUID) -> int:
        """Calculate book progress based on completed chapters.
        
        Returns percentage (0-100) of completed chapters.
        """
        # Count total and completed chapters
        stats_query = select(
            func.count(BookChapter.id).label("total"),
            func.count(BookChapter.id).filter(BookChapter.status == "done").label("completed")
        ).where(BookChapter.book_id == book_id)

        result = await self.session.execute(stats_query)
        stats = result.first()

        if not stats or stats.total == 0:
            # Fallback to page-based progress if no chapters
            query = select(BookProgress.progress_percentage).where(
                BookProgress.book_id == book_id
            ).order_by(BookProgress.updated_at.desc()).limit(1)
            result = await self.session.execute(query)
            progress = result.scalar()
            return int(progress or 0)

        return int((stats.completed / stats.total) * 100)

    async def get_flashcard_progress(self, deck_id: UUID) -> int:
        """Calculate flashcard progress.
        
        Currently returns 0 as flashcards use a different progress model
        based on due/overdue cards calculated on the frontend.
        """
        # TODO: Implement server-side flashcard progress if needed
        return 0

    async def get_content_progress(self, content_type: str, content_id: str | UUID) -> int:
        """Get progress for any content type.
        
        Args:
            content_type: One of 'course', 'book', 'youtube', 'flashcards'
            content_id: The UUID of the content (as string or UUID)
            
        Returns
        -------
            Progress percentage (0-100)
        """
        # Convert string to UUID if needed
        if isinstance(content_id, str):
            try:
                content_id = UUID(content_id)
            except ValueError:
                # Invalid UUID format
                return 0

        if content_type == "course":
            return await self.get_course_progress(content_id)
        if content_type == "youtube":
            return await self.get_video_progress(content_id)
        if content_type == "book":
            return await self.get_book_progress(content_id)
        if content_type == "flashcards":
            return await self.get_flashcard_progress(content_id)
        return 0

    async def bulk_get_progress(self, items: list[tuple[str, UUID]]) -> dict[str, int]:
        """Get progress for multiple items efficiently.
        
        Args:
            items: List of (content_type, content_id) tuples
            
        Returns
        -------
            Dictionary mapping "type:id" to progress percentage
        """
        results = {}

        # Group by type for efficient querying
        courses = [id for type, id in items if type == "course"]
        videos = [id for type, id in items if type == "youtube"]
        books = [id for type, id in items if type == "book"]

        # Batch query for courses
        if courses:
            # This could be optimized further with a single complex query
            for course_id in courses:
                progress = await self.get_course_progress(course_id)
                results[f"course:{course_id}"] = progress

        # Batch query for videos
        if videos:
            for video_id in videos:
                progress = await self.get_video_progress(video_id)
                results[f"youtube:{video_id}"] = progress

        # Batch query for books
        if books:
            for book_id in books:
                progress = await self.get_book_progress(book_id)
                results[f"book:{book_id}"] = progress

        return results
