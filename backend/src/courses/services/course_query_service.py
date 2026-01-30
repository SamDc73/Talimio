"""Course query service for read operations on courses."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select

from src.courses.models import Course, Lesson
from src.courses.schemas import CourseResponse
from src.courses.services.course_response_builder import CourseResponseBuilder


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CourseQueryService:
    """Service for querying course data."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.response_builder = CourseResponseBuilder(session)
        self._logger = logging.getLogger(__name__)

    async def get_course(self, course_id: UUID, user_id: UUID) -> CourseResponse:
        """Get a specific course by ID."""
        course_query = select(Course).where(Course.id == course_id, Course.user_id == user_id)
        course_result = await self.session.execute(course_query)
        course = course_result.scalar_one_or_none()

        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

        lessons_query = (
            select(Lesson)
            .where(Lesson.course_id == course_id)
            .order_by(*Lesson.course_order_by())
        )
        lessons_result = await self.session.execute(lessons_query)
        lessons = lessons_result.scalars().all()

        return self.response_builder.build_course_response(course, lessons)

    async def list_courses(
        self,
        page: int = 1,
        per_page: int = 20,
        search: str | None = None,
        user_id: UUID | None = None,
    ) -> tuple[list[CourseResponse], int]:
        """List courses with pagination and optional search."""
        if not user_id:
            return [], 0

        offset = (page - 1) * per_page

        base_query = select(Course).where(Course.user_id == user_id)
        count_query = select(func.count(Course.id)).where(Course.user_id == user_id)

        if search:
            search_pattern = f"%{search}%"
            base_query = base_query.where(Course.title.ilike(search_pattern) | Course.description.ilike(search_pattern))
            count_query = count_query.where(Course.title.ilike(search_pattern) | Course.description.ilike(search_pattern))

        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        course_query = base_query.order_by(Course.created_at.desc()).offset(offset).limit(per_page)
        course_result = await self.session.execute(course_query)
        courses = course_result.scalars().all()

        course_responses = self.response_builder.build_course_list(courses)
        return course_responses, total
