"""Lesson deletion service for deleting lessons."""

import logging
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.courses.models import Node


class LessonDeletionService:
    """Service for deleting lessons."""

    def __init__(self, session: AsyncSession, user_id: UUID | None = None) -> None:
        """Initialize the lesson deletion service.

        Args:
            session: Database session
            user_id: User ID for user-specific operations
        """
        self.session = session
        self.user_id = user_id
        self._logger = logging.getLogger(__name__)

    async def delete_lesson(
        self,
        course_id: UUID,
        lesson_id: UUID,
        user_id: UUID | None = None
    ) -> bool:
        """Delete a lesson.

        Args:
            course_id: Course ID
            lesson_id: Lesson ID
            user_id: User ID (optional override)

        Returns
        -------
            True if deleted successfully

        Raises
        ------
            HTTPException: If lesson not found
        """
        # Get lesson
        lesson_query = select(Node).where(
            Node.id == lesson_id,
            Node.roadmap_id == course_id,
            Node.parent_id.is_not(None)
        )
        lesson_result = await self.session.execute(lesson_query)
        lesson = lesson_result.scalar_one_or_none()

        if not lesson:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lesson not found"
            )

        await self.session.delete(lesson)
        await self.session.commit()

        return True
