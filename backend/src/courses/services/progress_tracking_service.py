"""Progress tracking service for course and lesson progress management."""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.courses.models import LessonProgress as Progress, Roadmap
from src.courses.schemas import (
    CourseProgressResponse,
    LessonStatusResponse,
    LessonStatusUpdate,
)
from src.courses.services.course_progress_service import CourseProgressService
from src.courses.services.course_progress_tracker import CourseProgressTracker


class ProgressTrackingService:
    """Service for managing course and lesson progress tracking."""

    def __init__(self, session: AsyncSession, user_id: UUID | None = None) -> None:
        """Initialize the progress tracking service.

        Args:
            session: Database session
            user_id: User ID for user-specific operations
        """
        self.session = session
        self.user_id = user_id
        self._logger = logging.getLogger(__name__)

    async def get_course_progress(
        self,
        course_id: UUID,
        user_id: UUID | None = None
    ) -> CourseProgressResponse:
        """Get overall progress for a course.

        Args:
            course_id: Course ID
            user_id: User ID (optional override)

        Returns
        -------
            Course progress response

        Raises
        ------
            HTTPException: If course not found
        """
        effective_user_id = user_id or self.user_id

        if not effective_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID required for progress tracking"
            )

        # Verify course exists
        course_query = select(Roadmap).where(Roadmap.id == course_id)
        course_result = await self.session.execute(course_query)
        course = course_result.scalar_one_or_none()

        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found"
            )

        from src.courses.services.course_management_service import CourseManagementService
        from src.courses.services.lesson_query_service import LessonQueryService

        course_service = CourseManagementService(self.session, effective_user_id)
        lesson_service = LessonQueryService(self.session, effective_user_id)

        modules = await course_service.list_modules(course_id, effective_user_id)
        lessons = await lesson_service.list_lessons(course_id, effective_user_id)

        # Use the existing progress service to calculate progress
        progress_service = CourseProgressService(self.session, effective_user_id)
        progress_data = await progress_service.get_course_progress(course_id, modules, lessons, effective_user_id)

        return CourseProgressResponse(
            course_id=str(course_id),
            total_modules=progress_data["total_modules"],
            completed_modules=progress_data.get("completed_modules", 0),
            in_progress_modules=progress_data.get("in_progress_modules", 0),
            completion_percentage=progress_data["completion_percentage"],
            total_lessons=progress_data["total_lessons"],
            completed_lessons=progress_data["completed_lessons"],
        )

    async def update_lesson_status(
        self,
        course_id: UUID,
        module_id: UUID,
        lesson_id: UUID,
        request: LessonStatusUpdate,
        user_id: UUID | None = None
    ) -> LessonStatusResponse:
        """Update the status of a specific lesson.

        Args:
            course_id: Course ID
            module_id: Module ID
            lesson_id: Lesson ID
            request: Status update request
            user_id: User ID (optional override)

        Returns
        -------
            Updated lesson status response

        Raises
        ------
            HTTPException: If lesson not found or update fails
        """
        effective_user_id = user_id or self.user_id

        if not effective_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID required for progress tracking"
            )

        # Verify course exists
        course_query = select(Roadmap).where(Roadmap.id == course_id)
        course_result = await self.session.execute(course_query)
        if not course_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found"
            )

        # Get or create lesson progress record
        # Note: course_id field in the database actually stores module_id
        progress_query = select(Progress).where(
            Progress.user_id == effective_user_id,
            Progress.course_id == str(module_id),  # course_id field stores module_id
            Progress.lesson_id == str(lesson_id)
        )

        progress_result = await self.session.execute(progress_query)
        progress = progress_result.scalar_one_or_none()

        if not progress:
            # Create new progress record
            # Note: course_id field stores module_id in the database
            progress = Progress(
                user_id=effective_user_id,
                course_id=str(module_id),  # course_id field stores module_id
                lesson_id=str(lesson_id),
                status=request.status,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            self.session.add(progress)
        else:
            # Update existing progress
            progress.status = request.status
            progress.updated_at = datetime.now(UTC)

        await self.session.commit()

        return LessonStatusResponse(
            lesson_id=str(lesson_id),
            module_id=str(module_id),
            course_id=str(course_id),
            status=progress.status,
            created_at=progress.created_at,
            updated_at=progress.updated_at,
        )

    async def get_lesson_status(
        self,
        course_id: UUID,
        module_id: UUID,
        lesson_id: UUID,
        user_id: UUID | None = None
    ) -> LessonStatusResponse:
        """Get the status of a specific lesson.

        Args:
            course_id: Course ID
            module_id: Module ID
            lesson_id: Lesson ID
            user_id: User ID (optional override)

        Returns
        -------
            Lesson status response

        Raises
        ------
            HTTPException: If lesson not found
        """
        effective_user_id = user_id or self.user_id

        if not effective_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID required for progress tracking"
            )

        # Verify course exists
        course_query = select(Roadmap).where(Roadmap.id == course_id)
        course_result = await self.session.execute(course_query)
        if not course_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found"
            )

        # Get lesson progress
        # Note: course_id field in the database actually stores module_id
        progress_query = select(Progress).where(
            Progress.user_id == effective_user_id,
            Progress.course_id == str(module_id),  # course_id field stores module_id
            Progress.lesson_id == str(lesson_id)
        )

        progress_result = await self.session.execute(progress_query)
        progress = progress_result.scalar_one_or_none()

        if not progress:
            # Return default status if no progress record exists
            now = datetime.now(UTC)
            return LessonStatusResponse(
                lesson_id=str(lesson_id),
                module_id=str(module_id),
                course_id=str(course_id),
                status="not_started",
                created_at=now,
                updated_at=now,
            )

        return LessonStatusResponse(
            lesson_id=str(lesson_id),
            module_id=str(module_id),
            course_id=str(course_id),
            status=progress.status,
            created_at=progress.created_at,
            updated_at=progress.updated_at,
        )

    async def get_all_lesson_statuses(
        self,
        course_id: UUID,
        user_id: UUID | None = None
    ) -> dict[str, str]:
        """Get all lesson statuses for a course.

        Args:
            course_id: Course ID
            user_id: User ID (optional override)

        Returns
        -------
            Dictionary mapping lesson IDs to their statuses

        Raises
        ------
            HTTPException: If course not found
        """
        effective_user_id = user_id or self.user_id

        if not effective_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID required for progress tracking"
            )

        # Verify course exists
        course_query = select(Roadmap).where(Roadmap.id == course_id)
        course_result = await self.session.execute(course_query)
        if not course_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found"
            )

        # Get all lessons for the course through the lesson service
        from src.courses.services.lesson_query_service import LessonQueryService
        lesson_service = LessonQueryService(self.session, effective_user_id)
        lessons = await lesson_service.list_lessons(course_id, effective_user_id)

        # Get progress for each lesson
        # Note: Progress.course_id field actually stores module_id
        lesson_ids = [str(lesson.id) for lesson in lessons]
        progress_query = select(Progress).where(
            Progress.user_id == effective_user_id,
            Progress.lesson_id.in_(lesson_ids)
        )

        progress_result = await self.session.execute(progress_query)
        progress_records = progress_result.scalars().all()

        # Create mapping of lesson_id to status
        status_map = {}
        for progress in progress_records:
            status_map[str(progress.lesson_id)] = progress.status

        # For lessons without progress records, set default status
        for lesson in lessons:
            lesson_id_str = str(lesson.id)
            if lesson_id_str not in status_map:
                status_map[lesson_id_str] = "not_started"

        return status_map

    async def update_course_progress(
        self,
        course_id: UUID,
        user_id: UUID | None,
        progress_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update course progress using the unified progress system.

        Args:
            course_id: Course ID
            user_id: User ID
            progress_data: Progress update data

        Returns
        -------
            Updated progress data
        """
        effective_user_id = user_id or self.user_id

        if not effective_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID required for progress tracking"
            )

        # Use the unified course progress tracker
        tracker = CourseProgressTracker()
        return await tracker.update_progress(course_id, effective_user_id, progress_data)

    async def calculate_course_progress(
        self,
        course_id: UUID,
        user_id: UUID | None
    ) -> float:
        """Calculate course completion percentage using unified progress system.

        Args:
            course_id: Course ID
            user_id: User ID

        Returns
        -------
            Completion percentage (0-100)
        """
        effective_user_id = user_id or self.user_id

        if not effective_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User ID required for progress tracking"
            )

        # Use the unified course progress tracker
        tracker = CourseProgressTracker()
        return await tracker.calculate_completion_percentage(course_id, effective_user_id)

    async def get_lesson_progress(
        self,
        lesson_id: UUID,
        _user_id: UUID | None
    ) -> dict[str, Any]:
        """Get lesson progress (stub for compatibility)."""
        # This is a placeholder - individual lesson progress is tracked as part of course progress
        return {
            "lesson_id": str(lesson_id),
            "status": "not_started",
            "completed": False
        }

    async def mark_lesson_complete(
        self,
        lesson_id: UUID,
        _user_id: UUID | None
    ) -> dict[str, Any]:
        """Mark lesson as complete (stub for compatibility)."""
        # This is a placeholder - will be replaced with proper implementation
        return {
            "lesson_id": str(lesson_id),
            "status": "completed",
            "success": True
        }
