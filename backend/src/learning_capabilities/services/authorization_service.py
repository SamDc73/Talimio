"""Authorization helpers for learning capability execution."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.courses.models import Course, Lesson
from src.learning_capabilities.errors import LearningCapabilitiesNotFoundError


class LearningCapabilityAuthorizationService:
    """Resolve owned resources for a request-scoped user."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def require_owned_course(self, *, user_id: uuid.UUID, course_id: uuid.UUID) -> Course:
        """Return an owned course or raise not-found."""
        course = await self._session.scalar(
            select(Course).where(
                Course.id == course_id,
                Course.user_id == user_id,
            )
        )
        if course is None:
            detail = "Course not found"
            raise LearningCapabilitiesNotFoundError(detail)
        return course

    async def require_owned_lesson(
        self,
        *,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> tuple[Course, Lesson]:
        """Return an owned (course, lesson) pair or raise not-found."""
        course = await self.require_owned_course(user_id=user_id, course_id=course_id)
        lesson = await self._session.scalar(
            select(Lesson).where(
                Lesson.id == lesson_id,
                Lesson.course_id == course.id,
            )
        )
        if lesson is None:
            detail = "Lesson not found"
            raise LearningCapabilitiesNotFoundError(detail)
        return course, lesson
