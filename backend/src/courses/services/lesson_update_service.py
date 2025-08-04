"""Lesson update service for updating lesson metadata and content."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.courses.models import Node
from src.courses.schemas import LessonResponse, LessonUpdate


class LessonUpdateService:
    """Service for updating lessons."""

    def __init__(self, session: AsyncSession, user_id: UUID | None = None) -> None:
        """Initialize the lesson update service.

        Args:
            session: Database session
            user_id: User ID for user-specific operations
        """
        self.session = session
        self.user_id = user_id
        self._logger = logging.getLogger(__name__)

    async def update_lesson(
        self, course_id: UUID, lesson_id: UUID, request: LessonUpdate, _user_id: UUID | None = None
    ) -> LessonResponse:
        """Update lesson metadata/content.

        Args:
            course_id: Course ID
            lesson_id: Lesson ID
            request: Update request
            user_id: User ID (optional override)

        Returns
        -------
            Updated lesson response

        Raises
        ------
            HTTPException: If lesson not found or update fails
        """
        # Get lesson
        lesson_query = select(Node).where(
            Node.id == lesson_id, Node.roadmap_id == course_id, Node.parent_id.is_not(None)
        )
        lesson_result = await self.session.execute(lesson_query)
        lesson = lesson_result.scalar_one_or_none()

        if not lesson:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

        # Update fields if provided
        if request.slug is not None:
            lesson.title = request.slug.replace("-", " ").title()
        if request.md_source is not None:
            lesson.content = request.md_source

        lesson.updated_at = datetime.now(UTC)

        await self.session.commit()

        return LessonResponse(
            id=lesson.id,
            course_id=course_id,
            module_id=lesson.parent_id,
            title=lesson.title,
            description=lesson.description,
            slug=lesson.title.lower().replace(" ", "-"),
            md_source=lesson.content or "",
            html_cache=None,
            citations=[],
            created_at=lesson.created_at,
            updated_at=lesson.updated_at,
        )
