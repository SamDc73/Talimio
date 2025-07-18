"""Lesson query service for read operations on lessons."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.client import AIError, create_lesson_body
from src.courses.models import Node, Roadmap
from src.courses.schemas import LessonResponse


class LessonQueryService:
    """Service for querying lesson data."""

    def __init__(self, session: AsyncSession, user_id: str | None = None) -> None:
        """Initialize the lesson query service.

        Args:
            session: Database session
            user_id: User ID for user-specific operations
        """
        self.session = session
        self.user_id = user_id
        self._logger = logging.getLogger(__name__)

    async def list_lessons(self, course_id: UUID, user_id: str | None = None) -> list[LessonResponse]:
        """List all lessons for a course.

        Args:
            course_id: Course ID
            user_id: User ID (optional override)

        Returns
        -------
            List of lesson responses

        Raises
        ------
            HTTPException: If course not found
        """
        # Verify course exists
        course_query = select(Roadmap).where(Roadmap.id == course_id)

        course_result = await self.session.execute(course_query)
        if not course_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found"
            )

        # Get all lessons for the course
        lessons_query = select(Node).where(
            Node.roadmap_id == course_id,
            Node.parent_id.is_not(None)  # Lessons have a parent module
        ).order_by(Node.order)

        lessons_result = await self.session.execute(lessons_query)
        lessons = lessons_result.scalars().all()

        return [
            LessonResponse(
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
            for lesson in lessons
        ]

    async def get_lesson(
        self,
        course_id: UUID,
        lesson_id: UUID,
        generate: bool = False,
        user_id: str | None = None
    ) -> LessonResponse:
        """Get a specific lesson, optionally generating if missing.

        Args:
            course_id: Course ID
            lesson_id: Lesson ID
            generate: Whether to generate content if missing
            user_id: User ID (optional override)

        Returns
        -------
            Lesson response

        Raises
        ------
            HTTPException: If lesson not found
        """
        # Verify course exists
        course_query = select(Roadmap).where(Roadmap.id == course_id)

        course_result = await self.session.execute(course_query)
        course = course_result.scalar_one_or_none()
        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found"
            )

        # Get the lesson
        lesson_query = select(Node).where(
            Node.id == lesson_id,
            Node.roadmap_id == course_id,
            Node.parent_id.is_not(None)  # Lessons have a parent module
        )

        lesson_result = await self.session.execute(lesson_query)
        lesson = lesson_result.scalar_one_or_none()

        if not lesson:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lesson not found"
            )

        # Generate content if requested and missing
        if generate and not lesson.content:
            try:
                # Get module context for better generation
                module_query = select(Node).where(Node.id == lesson.parent_id)
                module_result = await self.session.execute(module_query)
                module = module_result.scalar_one_or_none()

                context = {
                    "course_title": course.title,
                    "course_description": course.description,
                    "module_title": module.title if module else "",
                    "module_description": module.description if module else "",
                    "lesson_title": lesson.title,
                    "lesson_description": lesson.description,
                }

                content = await create_lesson_body(context)
                lesson.content = content
                lesson.updated_at = datetime.now(UTC)
                await self.session.commit()

            except AIError as e:
                self._logger.exception("Failed to generate lesson content: %s", e)
                # Continue without content rather than failing

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

    async def get_lesson_simplified(
        self,
        course_id: UUID,
        lesson_id: UUID,
        generate: bool = False,
        user_id: str | None = None
    ) -> LessonResponse:
        """Get a lesson without requiring module_id (searches through modules).

        Args:
            course_id: Course ID
            lesson_id: Lesson ID
            generate: Whether to generate content if missing
            user_id: User ID (optional override)

        Returns
        -------
            Lesson response

        Raises
        ------
            HTTPException: If lesson not found
        """
        effective_user_id = user_id or self.user_id

        # Verify course exists
        course_query = select(Roadmap).where(Roadmap.id == course_id)

        course_result = await self.session.execute(course_query)
        if not course_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found"
            )

        # Find lesson across all modules in the course
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
                detail="Lesson not found in this course"
            )

        # Use the regular get_lesson method
        return await self.get_lesson(course_id, lesson_id, generate, effective_user_id)
