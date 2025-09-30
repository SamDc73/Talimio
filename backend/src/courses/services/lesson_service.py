"""Lesson service with SQL-first queries and mandatory user isolation."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.client import LLMClient
from src.auth.context import AuthContext
from src.courses.models import Course, Node
from src.courses.schemas import LessonResponse


logger = logging.getLogger(__name__)


class LessonService:
    """Lesson service with SQL-first queries and mandatory user isolation."""

    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        """Initialize with user context for security isolation."""
        self.session = session
        self.user_id = user_id

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
        if generate and not (lesson.content and lesson.content.strip()):
            lesson = await self._generate_content_secure(lesson, course)

        return LessonResponse(
            id=lesson.id,
            course_id=course.id,
            module_id=lesson.parent_id or lesson.id,
            title=lesson.title,
            description=lesson.description,
            content=lesson.content,
            html_cache=None,
            citations=[],
            created_at=lesson.created_at,
            updated_at=lesson.updated_at,
        )

    async def _generate_content_secure(self, lesson: Node, course: Course) -> Node:
        """Generate content with conditional update to prevent concurrent writes.

        Uses LLMClient with AuthContext and only updates the lesson if content is
        still empty, to avoid race conditions across concurrent requests.
        """
        # Build minimal context
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

            # Create auth context for RAG enrichment
            auth = AuthContext(self.user_id, self.session)

            llm_client = LLMClient()
            lesson_content = await llm_client.create_lesson(context, auth)
            content = lesson_content.body

            # Conditional update - only set content if still empty
            update_stmt = (
                update(Node)
                .where(
                    Node.id == lesson.id,
                    or_(Node.content.is_(None), Node.content == ""),
                )
                .values(content=content, updated_at=datetime.now(UTC))
            )

            update_result = await self.session.execute(update_stmt)
            updated_rows = update_result.rowcount

            if updated_rows and updated_rows > 0:
                await self.session.commit()
                # Refresh to get persisted values
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
                # Another process already generated content; refresh to load it
                logger.info(
                    "Content already generated by another process",
                    extra={"user_id": str(self.user_id), "lesson_id": str(lesson.id)},
                )
                await self.session.refresh(lesson)

        except ValueError as e:
            # Validation errors (bad input, MDX issues)
            logger.exception(
                "Validation error generating lesson content: %s", str(e), extra={"user_id": str(self.user_id), "lesson_id": str(lesson.id)}
            )
            raise HTTPException(status_code=400, detail=f"Invalid lesson content: {e}") from e
        except RuntimeError as e:
            # System errors (API failures, network issues, timeouts)
            logger.exception(
                "System error generating lesson content: %s", str(e), extra={"user_id": str(self.user_id), "lesson_id": str(lesson.id)}
            )
            raise HTTPException(status_code=503, detail="Unable to generate lesson content. Please try again.") from e
        except Exception as e:
            logger.exception(
                "Unexpected error generating lesson content",
                extra={"user_id": str(self.user_id), "lesson_id": str(lesson.id)},
            )
            raise HTTPException(status_code=500, detail="An unexpected error occurred while generating lesson content") from e

        return lesson
