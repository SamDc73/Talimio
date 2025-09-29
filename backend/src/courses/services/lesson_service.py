"""Lesson service with SQL-first queries and mandatory user isolation."""

import logging
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.courses.models import Course, Node
from src.courses.schemas import LessonResponse
from src.courses.services.lesson_query_service import LessonQueryService


logger = logging.getLogger(__name__)


class LessonService:
    """Lesson service with SQL-first queries and mandatory user isolation."""

    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        """Initialize with user context for security isolation."""
        self.session = session
        self.user_id = user_id
        # Use existing secure LessonQueryService for generation logic
        self.lesson_query_service = LessonQueryService(session)

    async def get_lesson(self, course_id: UUID, lesson_id: UUID, generate: bool = False) -> LessonResponse:
        """Get lesson with single query including user isolation.

        Args:
            course_id: Course UUID
            lesson_id: Lesson UUID
            generate: Whether to generate content if missing

        Returns
        -------
            LessonResponse containing lesson data

        Raises
        ------
            HTTPException: 404 if lesson not found or access denied
        """
        # Single query with USER ISOLATION - prevents data leakage
        query = (
            select(Node, Course)
            .join(Course, Node.roadmap_id == Course.id)
            .where(
                Node.id == lesson_id,
                Node.roadmap_id == course_id,
                Course.user_id == self.user_id,
            )
        )
        result = await self.session.execute(query)
        row = result.first()

        if not row:
            # Log security event with user context
            logger.warning(
                "LESSON_ACCESS_DENIED",
                extra={"user_id": str(self.user_id), "lesson_id": str(lesson_id), "course_id": str(course_id)},
            )
            raise HTTPException(status_code=404, detail="Lesson not found or access denied")

        lesson, course = row

        # Generate content with user-aware locking if needed
        if generate and (not lesson.content or len(lesson.content.strip()) == 0):
            lesson = await self._generate_content_secure(lesson, course)

        return LessonResponse(
            id=lesson.id,
            course_id=course.id,
            module_id=lesson.parent_id if lesson.parent_id else lesson.id,
            title=lesson.title,
            description=lesson.description,
            content=lesson.content,  # Fix: Include the content field!
            html_cache=None,
            citations=[],
            created_at=lesson.created_at,
            updated_at=lesson.updated_at,
        )

    async def _generate_content_secure(self, lesson: Node, course: Course) -> Node:
        """Generate content using existing secure generation logic.

        This method delegates to LessonQueryService for content generation while
        maintaining the single-query pattern. The lesson and course
        objects are already validated, so we can safely generate content.
        """
        # Delegate to the existing secure generation service which has:
        # - User-aware locking to prevent concurrent generation
        # - Retry mechanisms with exponential backoff
        # - Proper error handling and audit logging
        # - Adaptive context building for personalized content
        # Trigger generation via the existing service (handles locking, retries, logging)
        await self.lesson_query_service.get_lesson(course.id, lesson.id, generate=True)

        # Refresh the lesson from the DB to get the newly generated content and timestamps
        await self.session.refresh(lesson)
        return lesson
