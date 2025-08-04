"""Lesson creation service for creating and regenerating lessons."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.client import AIError, create_lesson_body
from src.courses.models import Node, Roadmap
from src.courses.schemas import LessonCreate, LessonResponse


class LessonCreationService:
    """Service for creating and regenerating lessons."""

    def __init__(self, session: AsyncSession, user_id: UUID | None = None) -> None:
        """Initialize the lesson creation service.

        Args:
            session: Database session
            user_id: User ID for user-specific operations
        """
        self.session = session
        self.user_id = user_id
        self._logger = logging.getLogger(__name__)

    async def generate_lesson(
        self, course_id: UUID, request: LessonCreate, _user_id: UUID | None = None
    ) -> LessonResponse:
        """Generate a new lesson for a course.

        Args:
            course_id: Course ID
            request: Lesson creation request
            user_id: User ID (optional override)

        Returns
        -------
            Generated lesson response

        Raises
        ------
            HTTPException: If generation fails
        """
        # Verify course exists
        course_query = select(Roadmap).where(Roadmap.id == course_id)

        course_result = await self.session.execute(course_query)
        course = course_result.scalar_one_or_none()
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

        # Verify module exists if provided
        module = None
        if hasattr(request, "module_id") and request.module_id:
            module_query = select(Node).where(
                Node.id == request.module_id,
                Node.roadmap_id == course_id,
                Node.parent_id.is_(None),  # Modules have no parent
            )
            module_result = await self.session.execute(module_query)
            module = module_result.scalar_one_or_none()
            if not module:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")

        # Check if lesson already exists
        existing_query = select(Node).where(
            Node.title == request.slug,  # Using slug as title for now
            Node.roadmap_id == course_id,
            Node.parent_id.is_not(None),
        )
        existing_result = await self.session.execute(existing_query)
        if existing_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Lesson with this title already exists")

        try:
            # Generate lesson content
            context = {
                "course_title": course.title,
                "course_description": course.description,
                "module_title": module.title if module else "",
                "module_description": module.description if module else "",
                "lesson_requirements": request.node_meta,
            }

            content, citations = await create_lesson_body(context)

            # Get next order index
            order_query = select(Node).where(Node.roadmap_id == course_id, Node.parent_id.is_not(None))
            if module:
                order_query = order_query.where(Node.parent_id == module.id)

            order_result = await self.session.execute(order_query)
            existing_lessons = order_result.scalars().all()
            next_order = len(existing_lessons)

            # Create lesson node
            lesson = Node(
                title=request.slug.replace("-", " ").title(),
                description=f"Generated lesson for {course.title}",
                roadmap_id=course_id,
                parent_id=module.id if module else None,
                order=next_order,
                content=content,
                status="not_started",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

            self.session.add(lesson)
            await self.session.commit()

            return LessonResponse(
                id=lesson.id,
                course_id=course_id,
                module_id=lesson.parent_id,
                title=lesson.title,
                description=lesson.description,
                slug=request.slug,
                md_source=lesson.content or "",
                html_cache=None,
                citations=[],
                created_at=lesson.created_at,
                updated_at=lesson.updated_at,
            )

        except AIError as e:
            self._logger.exception("Failed to generate lesson: %s", e)
            await self.session.rollback()
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI service error: {e!s}") from e
        except Exception as e:
            self._logger.exception("Unexpected error during lesson generation: %s", e)
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate lesson"
            ) from e

    async def regenerate_lesson(self, course_id: UUID, lesson_id: UUID, _user_id: UUID | None = None) -> LessonResponse:
        """Regenerate an existing lesson.

        Args:
            course_id: Course ID
            lesson_id: Lesson ID
            user_id: User ID (optional override)

        Returns
        -------
            Regenerated lesson response

        Raises
        ------
            HTTPException: If regeneration fails
        """
        # Get lesson node
        lesson_query = select(Node).where(
            Node.id == lesson_id, Node.roadmap_id == course_id, Node.parent_id.is_not(None)
        )
        lesson_result = await self.session.execute(lesson_query)
        lesson = lesson_result.scalar_one_or_none()

        if not lesson:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

        try:
            # Get course and module context
            course_query = select(Roadmap).where(Roadmap.id == course_id)
            course_result = await self.session.execute(course_query)
            course = course_result.scalar_one_or_none()

            module = None
            if lesson.parent_id:
                module_query = select(Node).where(Node.id == lesson.parent_id)
                module_result = await self.session.execute(module_query)
                module = module_result.scalar_one_or_none()

            # Regenerate content
            context = {
                "course_title": course.title,
                "course_description": course.description,
                "module_title": module.title if module else "",
                "module_description": module.description if module else "",
                "lesson_title": lesson.title,
                "lesson_description": lesson.description,
            }

            content, citations = await create_lesson_body(context)
            lesson.content = content
            # TODO: Store citations if needed
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

        except AIError as e:
            self._logger.exception("Failed to regenerate lesson: %s", e)
            await self.session.rollback()
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI service error: {e!s}") from e
