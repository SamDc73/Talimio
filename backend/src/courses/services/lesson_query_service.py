"""Lesson query service for read operations on lessons."""

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.client import AIError, create_lesson_body
from src.courses.models import Node, Roadmap
from src.courses.schemas import LessonResponse


# Module-level locks for user-aware concurrency control
_lesson_locks: dict[str, asyncio.Lock] = {}
_locks_lock = asyncio.Lock()


async def get_lesson_lock(user_id: UUID, lesson_id: UUID) -> asyncio.Lock:
    """Get or create a user-aware lesson lock to prevent cross-user contention.

    Args:
        user_id: User ID for isolation
        lesson_id: Lesson ID being processed

    Returns
    -------
        AsyncIO lock for this user-lesson combination
    """
    lock_key = f"{user_id}:{lesson_id}"
    async with _locks_lock:
        if lock_key not in _lesson_locks:
            _lesson_locks[lock_key] = asyncio.Lock()
        return _lesson_locks[lock_key]


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

    async def get_lesson(  # noqa: C901, PLR0912, PLR0915
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

        # Generate content if requested and missing (with user-aware concurrency control)
        if generate and (not lesson.content or len(lesson.content.strip()) == 0):
            if not effective_user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User authentication required for content generation",
                )

            # Acquire user-aware lock to prevent concurrent generation
            lesson_lock = await get_lesson_lock(effective_user_id, lesson_id)

            async with lesson_lock:
                self._logger.info(
                    "GEN_LOCK_ACQUIRED",
                    extra={"user_id": str(effective_user_id), "lesson_id": str(lesson_id), "course_id": str(course_id)},
                )

                # Re-check content after acquiring lock (another request might have generated it)
                # IMPORTANT: Avoid row-level locks here. Holding a DB lock while generating content
                # (which can take seconds) can block other transactions and lead to timeouts.
                # We rely on the conditional UPDATE below for optimistic concurrency control.
                fresh_query = select(Node).where(Node.id == lesson_id)  # no FOR UPDATE
                fresh_result = await self.session.execute(fresh_query)
                fresh_lesson = fresh_result.scalar_one_or_none()

                if fresh_lesson and fresh_lesson.content and len(fresh_lesson.content.strip()) > 0:
                    self._logger.info(
                        "GEN_SKIP_ALREADY_PRESENT",
                        extra={"user_id": str(effective_user_id), "lesson_id": str(lesson_id)},
                    )
                    lesson.content = fresh_lesson.content
                    lesson.updated_at = fresh_lesson.updated_at
                    return LessonResponse(
                        id=lesson.id,
                        course_id=course_id,
                        module_id=lesson.parent_id if lesson.parent_id else lesson.id,
                        title=lesson.title,
                        description=lesson.description,
                        content=fresh_lesson.content,
                        html_cache=None,
                        citations=[],
                        created_at=lesson.created_at,
                        updated_at=lesson.updated_at,
                    )

                # Proceed with generation
            # Build proper context that matches what create_lesson_body expects
            context = {
                "title": lesson.title,  # This is what _extract_lesson_metadata expects
                "description": lesson.description or "",
                "skill_level": course.skill_level or "beginner",
                "roadmap_id": str(course.id) if course.id else None,
                "course_title": course.title,
                "course_description": course.description,
                "original_user_prompt": course.description,  # Use course description as fallback
                "lesson_title": lesson.title,  # Add for adaptive context
                "lesson_requirements": {},  # Add empty requirements for adaptive context
            }

            # Add adaptive context if user_id is available
            if effective_user_id:
                from .adaptive_context_service import AdaptiveContextService

                adaptive_service = AdaptiveContextService(self.session, effective_user_id)
                adaptive_context = await adaptive_service.build_adaptive_context(context, effective_user_id, course_id)

                # Natural review injection
                if adaptive_context:
                    context.update(adaptive_context)

                    # Add review hints if weak concepts exist
                    if "natural_review" in adaptive_context:
                        weak_concepts = adaptive_context["natural_review"]["concepts"]
                        context["review_hints"] = f"Naturally reinforce: {', '.join(weak_concepts)}"

            # Retry mechanism with exponential backoff
            max_retries = 3
            retry_delay = 1.0  # Start with 1 second
            last_error = None

            for attempt in range(max_retries):
                try:
                    self._logger.info("Attempting to generate lesson content (attempt %d/%d)", attempt + 1, max_retries)
                    content, _ = await create_lesson_body(context)

                    if content and len(content.strip()) > 100:  # Validate content
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
                                "GEN_WRITE_UPDATED",
                                extra={
                                    "user_id": str(effective_user_id),
                                    "lesson_id": str(lesson_id),
                                    "updated": True,
                                    "attempt": attempt + 1,
                                },
                            )
                        else:
                            # Another process updated the content
                            self._logger.info(
                                "GEN_WRITE_UPDATED",
                                extra={
                                    "user_id": str(effective_user_id),
                                    "lesson_id": str(lesson_id),
                                    "updated": False,
                                    "reason": "content_already_generated",
                                },
                            )
                            # Refresh lesson with the content that was generated by another process
                            await self.session.refresh(lesson)

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
                    self._logger.exception(
                        "Unexpected error generating lesson content: %s",
                        e,
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
