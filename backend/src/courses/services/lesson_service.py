"""Lesson service with SQL-first queries and mandatory user isolation."""

import logging
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import HTTPException
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.client import LLMClient
from src.auth.context import AuthContext
from src.courses.models import Course, Lesson
from src.courses.schemas import LessonResponse


def _module_id(course_id: UUID, module_name: str | None) -> UUID:
    module_key = module_name or "default"
    return uuid5(NAMESPACE_URL, f"course-module:{course_id}:{module_key}")


logger = logging.getLogger(__name__)


class LessonService:
    """Lesson service with SQL-first queries and mandatory user isolation."""

    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        """Initialize with user context for security isolation."""
        self.session = session
        self.user_id = user_id

    async def get_lesson(
        self,
        course_id: UUID,
        lesson_id: UUID,
        force_refresh: bool = False,
    ) -> LessonResponse:
        """Get lesson with single query including user isolation.

        Args:
            course_id: Course UUID
            lesson_id: Lesson UUID
            force_refresh: Whether to regenerate content even if it already exists

        Returns
        -------
            LessonResponse containing lesson data

        Raises
        ------
            HTTPException: 404 if lesson not found or access denied
        """
        # Single query with USER ISOLATION - prevents data leakage
        query = (
            select(Lesson, Course)
            .join(Course, Lesson.course_id == Course.id)
            .where(
                Lesson.id == lesson_id,
                Lesson.course_id == course_id,
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

        if force_refresh or not (lesson.content and lesson.content.strip()):
            lesson = await self._generate_content_secure(lesson, course, force=force_refresh)

        module_id = _module_id(course.id, lesson.module_name)

        return LessonResponse(
            id=lesson.id,
            course_id=course.id,
            module_id=module_id,
            module_name=lesson.module_name,
            module_order=lesson.module_order,
            order=lesson.order,
            title=lesson.title,
            description=lesson.description,
            content=lesson.content,
            html_cache=None,
            citations=[],
            created_at=lesson.created_at,
            updated_at=lesson.updated_at,
        )

    async def _generate_content_secure(self, lesson: Lesson, course: Course, force: bool = False) -> Lesson:
        """Generate content with conditional update to prevent concurrent writes."""
        if not force and lesson.content and lesson.content.strip():
            return lesson

        context = {
            "title": lesson.title,
            "description": lesson.description or "",
            "course_id": str(course.id),
            "course_title": course.title,
            "user_id": self.user_id,
        }

        try:
            logger.info(
                "Generating lesson content",
                extra={
                    "user_id": str(self.user_id),
                    "lesson_id": str(lesson.id),
                    "lesson_title": lesson.title,
                },
            )

            auth = AuthContext(self.user_id, self.session)
            llm_client = LLMClient()
            lesson_content = await llm_client.create_lesson(context, auth)
            content = lesson_content.body

            conditions = [Lesson.id == lesson.id]
            if not force:
                conditions.append(or_(Lesson.content.is_(None), Lesson.content == ""))

            update_stmt = (
                update(Lesson)
                .where(*conditions)
                .values(content=content, updated_at=datetime.now(UTC))
            )

            update_result = await self.session.execute(update_stmt)
            updated_rows = getattr(update_result, "rowcount", None)

            if updated_rows and updated_rows > 0:
                await self.session.commit()
                await self.session.refresh(lesson)
                logger.info(
                    "Lesson content generated and saved",
                    extra={
                        "user_id": str(self.user_id),
                        "lesson_id": str(lesson.id),
                        "content_length": len(content) if content else 0,
                    },
                )
            else:
                logger.info(
                    "Content already generated by another process",
                    extra={"user_id": str(self.user_id), "lesson_id": str(lesson.id)},
                )
                await self.session.refresh(lesson)

        except ValueError as exc:
            logger.exception(
                "Validation error generating lesson content: %s",
                str(exc),
                extra={"user_id": str(self.user_id), "lesson_id": str(lesson.id)},
            )
            raise HTTPException(status_code=400, detail=f"Invalid lesson content: {exc}") from exc
        except RuntimeError as exc:
            logger.exception(
                "System error generating lesson content: %s",
                str(exc),
                extra={"user_id": str(self.user_id), "lesson_id": str(lesson.id)},
            )
            raise HTTPException(status_code=503, detail="Unable to generate lesson content. Please try again.") from exc
        except Exception as exc:
            logger.exception(
                "Unexpected error generating lesson content",
                extra={"user_id": str(self.user_id), "lesson_id": str(lesson.id)},
            )
            raise HTTPException(status_code=500, detail="An unexpected error occurred while generating lesson content") from exc

        return lesson

