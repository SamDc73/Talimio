"""Lesson query service for read operations on lessons."""

import asyncio
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

    def __init__(self, session: AsyncSession, user_id: UUID | None = None) -> None:
        """Initialize the lesson query service.

        Args:
            session: Database session
            user_id: User ID for user-specific operations
        """
        self.session = session
        self.user_id = user_id
        self._logger = logging.getLogger(__name__)

    async def list_lessons(self, course_id: UUID, _user_id: UUID | None = None) -> list[LessonResponse]:
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
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

        # Get all lessons for the course
        lessons_query = (
            select(Node)
            .where(
                Node.roadmap_id == course_id
                # Removed parent_id check - in simplified backend, modules ARE lessons
            )
            .order_by(Node.order)
        )

        lessons_result = await self.session.execute(lessons_query)
        lessons = lessons_result.scalars().all()

        return [
            LessonResponse(
                id=lesson.id,
                course_id=course_id,
                module_id=lesson.parent_id if lesson.parent_id else lesson.id,  # Use lesson.id if no parent
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

    async def get_lesson(  # noqa: C901
        self, course_id: UUID, lesson_id: UUID, generate: bool = False, _user_id: UUID | None = None
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
        # Validate required parameters
        if not course_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="course_id is required"
            )
        if not lesson_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="lesson_id is required"
            )

        # Verify course exists
        course_query = select(Roadmap).where(Roadmap.id == course_id)

        course_result = await self.session.execute(course_query)
        course = course_result.scalar_one_or_none()
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

        # Get the lesson
        lesson_query = select(Node).where(
            Node.id == lesson_id,
            Node.roadmap_id == course_id,
            # Removed parent_id check - in simplified backend, modules ARE lessons
        )

        lesson_result = await self.session.execute(lesson_query)
        lesson = lesson_result.scalar_one_or_none()

        if not lesson:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

        # Generate content if requested and missing
        if generate and not lesson.content:
            # Build proper context that matches what create_lesson_body expects
            context = {
                "title": lesson.title,  # This is what _extract_lesson_metadata expects
                "description": lesson.description or "",
                "skill_level": course.skill_level or "beginner",
                "roadmap_id": str(course.id) if course.id else None,
                "course_title": course.title,
                "course_description": course.description,
                "original_user_prompt": course.description,  # Use course description as fallback
            }

            # Retry mechanism with exponential backoff
            max_retries = 3
            retry_delay = 1.0  # Start with 1 second
            last_error = None

            for attempt in range(max_retries):
                try:
                    self._logger.info("Attempting to generate lesson content (attempt %d/%d)", attempt + 1, max_retries)
                    content, citations = await create_lesson_body(context)

                    if content and len(content.strip()) > 100:  # Validate content
                        lesson.content = content
                        # TODO: Store citations if needed
                        lesson.updated_at = datetime.now(UTC)
                        await self.session.commit()
                        self._logger.info("Successfully generated lesson content on attempt %d", attempt + 1)
                        break
                    msg = "Generated content is too short or empty"
                    raise AIError(msg)

                except AIError as e:
                    last_error = e
                    self._logger.warning(
                        "Failed to generate lesson content (attempt %d/%d): %s", attempt + 1, max_retries, str(e)
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    # All retries exhausted
                    self._logger.exception(
                        "Failed to generate lesson content after %d attempts: %s", max_retries, str(last_error)
                    )
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=f"Unable to generate lesson content at this time. Please try again later. Error: {last_error!s}",
                    ) from last_error
                except Exception as e:
                    # Catch any other unexpected errors
                    self._logger.exception("Unexpected error generating lesson content: %s", e)
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="An unexpected error occurred while generating lesson content",
                    ) from e

        return LessonResponse(
            id=lesson.id,
            course_id=course_id,
            module_id=lesson.parent_id if lesson.parent_id else lesson.id,  # Use lesson.id if no parent
            title=lesson.title,
            description=lesson.description,
            slug=lesson.title.lower().replace(" ", "-"),
            md_source=lesson.content or "",
            content=lesson.content or "",  # Also set content field for frontend compatibility
            html_cache=None,
            citations=[],
            created_at=lesson.created_at,
            updated_at=lesson.updated_at,
        )

    async def get_lesson_simplified(
        self, course_id: UUID, lesson_id: UUID, generate: bool = False, user_id: UUID | None = None
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
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

        # Find lesson across all modules in the course
        lesson_query = select(Node).where(
            Node.id == lesson_id,
            Node.roadmap_id == course_id,
            # Removed parent_id check - in simplified backend, modules ARE lessons
        )

        lesson_result = await self.session.execute(lesson_query)
        lesson = lesson_result.scalar_one_or_none()

        if not lesson:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found in this course")

        # Use the regular get_lesson method
        return await self.get_lesson(course_id, lesson_id, generate, effective_user_id)
