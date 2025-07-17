"""Course progress tracking service.

Handles progress tracking and status updates for courses, modules, and lessons.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.courses.models import LessonProgress as Progress
from src.courses.schemas import (
    CourseProgressResponse,
    LessonStatusResponse,
    LessonStatusUpdate,
)


class CourseProgressService:
    """Service for course progress tracking operations."""

    def __init__(self, session: AsyncSession, user_id: str | None = None) -> None:
        """Initialize the progress service.

        Args:
            session: Database session
            user_id: User ID for user-specific operations
        """
        self.session = session
        self.user_id = user_id

    async def get_course_progress(self, course_id: UUID, user_id: str | None = None) -> CourseProgressResponse:
        """Get overall progress for a course."""
        # Import here to avoid circular imports
        from src.courses.services.course_module_service import CourseModuleService

        module_service = CourseModuleService(self.session, user_id)

        # Get all modules for the course
        modules = await module_service.list_modules(course_id, user_id)
        total_modules = len(modules)
        completed_modules = len([m for m in modules if m.status == "completed"])
        in_progress_modules = len([m for m in modules if m.status == "in_progress"])

        # Get all lessons for all modules
        from src.courses.services.course_lesson_service import CourseLessonService

        lesson_service = CourseLessonService(self.session, user_id)

        total_lessons = 0
        completed_lessons = 0

        for module in modules:
            module_lessons = await lesson_service.list_lessons(course_id, module.id, user_id)
            total_lessons += len(module_lessons)

            # Count completed lessons by checking progress records
            for lesson in module_lessons:
                stmt = select(Progress).where(Progress.lesson_id == str(lesson.id), Progress.status == "completed")
                result = await self.session.execute(stmt)
                progress = result.scalar_one_or_none()
                if progress:
                    completed_lessons += 1

        completion_percentage = (completed_lessons / total_lessons * 100) if total_lessons > 0 else 0.0

        return CourseProgressResponse(
            course_id=course_id,
            total_modules=total_modules,
            completed_modules=completed_modules,
            in_progress_modules=in_progress_modules,
            completion_percentage=completion_percentage,
            total_lessons=total_lessons,
            completed_lessons=completed_lessons,
        )

    async def update_lesson_status(
        self,
        course_id: UUID,
        module_id: UUID,
        lesson_id: UUID,
        request: LessonStatusUpdate,
        _user_id: str | None = None,
    ) -> LessonStatusResponse:
        """Update the status of a specific lesson."""
        # Check if progress record exists
        stmt = select(Progress).where(
            Progress.lesson_id == str(lesson_id),
            Progress.course_id == str(course_id),
            Progress.module_id == str(module_id),
        )
        result = await self.session.execute(stmt)
        progress = result.scalar_one_or_none()

        now = datetime.now(UTC)

        if progress:
            # Update existing progress
            progress.status = request.status
            progress.updated_at = now
        else:
            # Create new progress record
            progress = Progress(
                lesson_id=str(lesson_id),
                course_id=str(course_id),
                module_id=str(module_id),
                status=request.status,
                created_at=now,
                updated_at=now,
            )
            self.session.add(progress)

        await self.session.commit()
        await self.session.refresh(progress)

        return LessonStatusResponse(
            lesson_id=lesson_id,
            module_id=module_id,
            course_id=course_id,
            status=progress.status,
            created_at=progress.created_at,
            updated_at=progress.updated_at,
        )

    async def get_course_progress_percentage(self, course_id: UUID, user_id: UUID) -> int:
        """Calculate course progress based on completed lessons.

        Returns percentage (0-100) of completed lessons.
        This matches the ProgressCalculator interface.
        """
        from sqlalchemy import String, func

        from src.courses.models import Node

        # Count total lessons (nodes with parent_id)
        total_query = select(func.count(Node.id)).where(Node.roadmap_id == course_id, Node.parent_id.is_not(None))
        total_result = await self.session.execute(total_query)
        total_lessons = total_result.scalar() or 0

        if total_lessons == 0:
            return 0

        # Create a subquery that gets the latest status per lesson
        # Handle legacy records with user_id = None for backward compatibility
        from src.config.settings import DEFAULT_USER_ID
        user_filter = (Progress.user_id == user_id) | (Progress.user_id.is_(None) if user_id == DEFAULT_USER_ID else False)

        latest_status_subquery = (
            select(
                Progress.lesson_id,
                Progress.status,
                func.row_number()
                .over(partition_by=Progress.lesson_id, order_by=Progress.updated_at.desc())
                .label("rn"),
            )
            .select_from(Progress)
            .join(Node, func.cast(Node.id, String) == Progress.lesson_id)
            .where(Node.roadmap_id == course_id, user_filter)
        ).subquery()

        # Count completed lessons (only the latest status per lesson)
        completed_query = (
            select(func.count())
            .select_from(latest_status_subquery)
            .where(latest_status_subquery.c.rn == 1, latest_status_subquery.c.status == "completed")
        )
        completed_result = await self.session.execute(completed_query)
        completed_lessons = completed_result.scalar() or 0

        return int((completed_lessons / total_lessons) * 100)

    async def get_lesson_completion_stats(self, course_id: UUID, user_id: UUID) -> dict:
        """Get detailed lesson completion statistics.

        Returns statistics about lesson completion for the course.
        """
        from sqlalchemy import String, func

        from src.courses.models import Node

        # Count total lessons (nodes with parent_id)
        total_query = select(func.count(Node.id)).where(Node.roadmap_id == course_id, Node.parent_id.is_not(None))
        total_result = await self.session.execute(total_query)
        total_lessons = total_result.scalar() or 0

        if total_lessons == 0:
            return {
                "total_lessons": 0,
                "completed_lessons": 0,
                "in_progress_lessons": 0,
                "not_started_lessons": 0,
                "completion_percentage": 0,
            }

        # Create a subquery that gets the latest status per lesson
        # Handle legacy records with user_id = None for backward compatibility
        from src.config.settings import DEFAULT_USER_ID
        user_filter = (Progress.user_id == user_id) | (Progress.user_id.is_(None) if user_id == DEFAULT_USER_ID else False)

        latest_status_subquery = (
            select(
                Progress.lesson_id,
                Progress.status,
                func.row_number()
                .over(partition_by=Progress.lesson_id, order_by=Progress.updated_at.desc())
                .label("rn"),
            )
            .select_from(Progress)
            .join(Node, func.cast(Node.id, String) == Progress.lesson_id)
            .where(Node.roadmap_id == course_id, user_filter)
        ).subquery()

        # Count lessons by status
        status_query = (
            select(
                latest_status_subquery.c.status,
                func.count().label("count")
            )
            .select_from(latest_status_subquery)
            .where(latest_status_subquery.c.rn == 1)
            .group_by(latest_status_subquery.c.status)
        )
        status_result = await self.session.execute(status_query)
        status_counts = {row.status: row.count for row in status_result.fetchall()}

        completed_lessons = status_counts.get("completed", 0)
        in_progress_lessons = status_counts.get("in_progress", 0)
        not_started_lessons = total_lessons - completed_lessons - in_progress_lessons

        return {
            "total_lessons": total_lessons,
            "completed_lessons": completed_lessons,
            "in_progress_lessons": in_progress_lessons,
            "not_started_lessons": not_started_lessons,
            "completion_percentage": int((completed_lessons / total_lessons) * 100) if total_lessons > 0 else 0,
        }

    async def get_lesson_status(
        self, course_id: UUID, module_id: UUID, lesson_id: UUID, _user_id: str | None = None
    ) -> LessonStatusResponse:
        """Get the status of a specific lesson."""
        stmt = select(Progress).where(
            Progress.lesson_id == str(lesson_id),
            Progress.course_id == str(course_id),
            Progress.module_id == str(module_id),
        )
        result = await self.session.execute(stmt)
        progress = result.scalar_one_or_none()

        if not progress:
            # Return default status if no progress record exists
            now = datetime.now(UTC)
            return LessonStatusResponse(
                lesson_id=lesson_id,
                module_id=module_id,
                course_id=course_id,
                status="not_started",
                created_at=now,
                updated_at=now,
            )

        return LessonStatusResponse(
            lesson_id=lesson_id,
            module_id=module_id,
            course_id=course_id,
            status=progress.status,
            created_at=progress.created_at,
            updated_at=progress.updated_at,
        )
