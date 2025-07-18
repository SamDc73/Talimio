"""Course update service for modification operations on courses."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.courses.models import Roadmap
from src.courses.schemas import CourseResponse, CourseUpdate
from src.courses.services.course_query_service import CourseQueryService


class CourseUpdateService:
    """Service for updating course data."""

    def __init__(self, session: AsyncSession, user_id: str | None = None) -> None:
        """Initialize the course update service.

        Args:
            session: Database session
            user_id: User ID for user-specific operations
        """
        self.session = session
        self.user_id = user_id
        self.query_service = CourseQueryService(session, user_id)
        self._logger = logging.getLogger(__name__)

    async def update_course(
        self,
        course_id: UUID,
        request: CourseUpdate,
        user_id: str | None = None
    ) -> CourseResponse:
        """Update a course.

        Args:
            course_id: Course ID
            request: Update request
            user_id: User ID (optional override)

        Returns
        -------
            Updated course response

        Raises
        ------
            HTTPException: If course not found or update fails
        """
        effective_user_id = user_id or self.user_id

        # Get the roadmap/course
        query = select(Roadmap).where(Roadmap.id == course_id)

        result = await self.session.execute(query)
        roadmap = result.scalar_one_or_none()

        if not roadmap:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found"
            )

        # Update fields if provided
        if request.title is not None:
            roadmap.title = request.title
        if request.description is not None:
            roadmap.description = request.description

        roadmap.updated_at = datetime.now(UTC)

        await self.session.commit()

        # Return updated course (get full course data)
        return await self.query_service.get_course(course_id, effective_user_id)
