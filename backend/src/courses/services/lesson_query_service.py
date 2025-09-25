"""Lesson query service for read operations on lessons."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.client import LLMClient
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
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="course_id is required")
        if not lesson_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="lesson_id is required")

        # Resolve effective user for optional ownership check
        effective_user_id = _user_id or self.user_id

        # Single JOIN query to validate lesson under course (+ optional ownership)
        query = (
            select(Node, Roadmap)
            .join(Roadmap, Node.roadmap_id == Roadmap.id)
            .where(
                Node.id == lesson_id,
                Node.roadmap_id == course_id,
            )
        )
        if effective_user_id:
            query = query.where(Roadmap.user_id == effective_user_id)

        result = await self.session.execute(query)
        row = result.first()
        if not row:
            # Preserve previous behavior/shape
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

        lesson, course = row

        # Generate content if requested and missing
        if generate and (not lesson.content or len(lesson.content.strip()) == 0):
            if not effective_user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User authentication required for content generation",
                )
            # Build context with only the fields that are actually used
            context = {
                "title": lesson.title,
                "description": lesson.description or "",
                "course_id": str(course.id) if course.id else None,
                "course_title": course.title,
                "user_id": effective_user_id,  # Add user_id directly here
            }

            # Let LiteLLM handle all timeout and error management
            try:
                self._logger.info(
                    "Generating lesson content",
                    extra={
                        "user_id": str(effective_user_id),
                        "lesson_id": str(lesson_id),
                        "lesson_title": lesson.title,
                    },
                )

                # Create auth context for RAG enrichment
                auth = None
                if effective_user_id:
                    from src.auth.context import AuthContext
                    auth = AuthContext(effective_user_id, self.session)

                llm_client = LLMClient()
                lesson_content = await llm_client.create_lesson(context, auth)
                content = lesson_content.body

                # Use conditional update to prevent double-write
                from sqlalchemy import update

                update_stmt = (
                    update(Node)
                    .where(
                        and_(
                            Node.id == lesson_id,
                            # Only update if content is still empty
                            Node.content.is_(None) | (Node.content == ""),
                        )
                    )
                    .values(content=content, updated_at=datetime.now(UTC))
                )

                update_result = await self.session.execute(update_stmt)
                updated_rows = update_result.rowcount

                if updated_rows > 0:
                    await self.session.commit()
                    lesson.content = content
                    lesson.updated_at = datetime.now(UTC)

                    self._logger.info(
                        "Lesson content generated and saved",
                        extra={
                            "user_id": str(effective_user_id),
                            "lesson_id": str(lesson_id),
                            "content_length": len(content),
                        },
                    )
                else:
                    # Another process already generated content
                    self._logger.info(
                        "Content already generated by another process",
                        extra={
                            "user_id": str(effective_user_id),
                            "lesson_id": str(lesson_id),
                        },
                    )
                    # Refresh to get the content
                    await self.session.refresh(lesson)

            except ValueError as e:
                # Validation errors (bad input, MDX issues)
                self._logger.exception(
                    "Validation error generating lesson content: %s",
                    str(e),
                    extra={"user_id": str(effective_user_id), "lesson_id": str(lesson_id)},
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid lesson content: {e}",
                ) from e
            except RuntimeError as e:
                # System errors (API failures, network issues, timeouts)
                self._logger.exception(
                    "System error generating lesson content: %s",
                    str(e),
                    extra={"user_id": str(effective_user_id), "lesson_id": str(lesson_id)},
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Unable to generate lesson content. Please try again.",
                ) from e
            except Exception as e:
                self._logger.exception(
                    "Unexpected error generating lesson content",
                    extra={"user_id": str(effective_user_id), "lesson_id": str(lesson_id)},
                )
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
            content=lesson.content,
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
        # Delegate to get_lesson to avoid duplicate DB lookups
        return await self.get_lesson(course_id, lesson_id, generate, effective_user_id)
