"""Course orchestrator service that coordinates all course-related operations.

This service implements the ICourseService interface and delegates to specialized services
for different aspects of course management.
"""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.courses.schemas import (
    CourseCreate,
    CourseProgressResponse,
    CourseResponse,
    CourseUpdate,
    LessonCreate,
    LessonResponse,
    LessonStatusResponse,
    LessonStatusUpdate,
    LessonUpdate,
    ModuleResponse,
)
from src.courses.services.course_management_service import CourseManagementService
from src.courses.services.interface import ICourseService
from src.courses.services.lesson_creation_service import LessonCreationService
from src.courses.services.lesson_deletion_service import LessonDeletionService
from src.courses.services.lesson_query_service import LessonQueryService
from src.courses.services.lesson_update_service import LessonUpdateService
from src.courses.services.progress_tracking_service import ProgressTrackingService


class CourseOrchestratorService(ICourseService):
    """Main course service that orchestrates all course-related operations.

    This service implements the ICourseService interface and delegates operations
    to specialized services for better organization and maintainability.
    """

    def __init__(self, session: AsyncSession, user_id: UUID | None = None) -> None:
        """Initialize the course orchestrator service.

        Args:
            session: Database session
            user_id: User ID for user-specific operations
        """
        self.session = session
        self.user_id = user_id
        self._logger = logging.getLogger(__name__)

        # Initialize specialized services
        self.course_management = CourseManagementService(session, user_id)
        self.lesson_query = LessonQueryService(session, user_id)
        self.lesson_creation = LessonCreationService(session, user_id)
        self.lesson_update = LessonUpdateService(session, user_id)
        self.lesson_deletion = LessonDeletionService(session, user_id)
        self.progress_tracking = ProgressTrackingService(session, user_id)

    # Course operations
    async def create_course(self, request: CourseCreate, user_id: UUID | None = None) -> CourseResponse:
        """Create a new course using AI generation."""
        return await self.course_management.create_course(request, user_id)

    async def get_course(self, course_id: UUID, user_id: UUID | None = None) -> CourseResponse:
        """Get a specific course by ID."""
        return await self.course_management.get_course(course_id, user_id)

    async def list_courses(
        self, page: int = 1, per_page: int = 20, search: str | None = None, user_id: UUID | None = None
    ) -> tuple[list[CourseResponse], int]:
        """List courses with pagination and optional search."""
        return await self.course_management.list_courses(page, per_page, search, user_id)

    async def update_course(self, course_id: UUID, request: CourseUpdate, user_id: UUID | None = None) -> CourseResponse:
        """Update a course."""
        return await self.course_management.update_course(course_id, request, user_id)

    async def delete_course(self, course_id: UUID, user_id: UUID | None = None) -> None:
        """Delete a course and all its associated data."""
        await self.course_management.delete_course(course_id, user_id)

    # Module operations
    async def list_modules(self, course_id: UUID, user_id: UUID | None = None) -> list[ModuleResponse]:
        """List all modules for a course."""
        return await self.course_management.list_modules(course_id, user_id)

    # Lesson operations
    async def list_lessons(self, course_id: UUID, user_id: UUID | None = None) -> list[LessonResponse]:
        """List all lessons for a course."""
        return await self.lesson_query.list_lessons(course_id, user_id)

    async def get_lesson(
        self, course_id: UUID, lesson_id: UUID, generate: bool = False, user_id: UUID | None = None
    ) -> LessonResponse:
        """Get a specific lesson, optionally generating if missing."""
        return await self.lesson_query.get_lesson(course_id, lesson_id, generate, user_id)

    async def get_lesson_simplified(
        self, course_id: UUID, lesson_id: UUID, generate: bool = False, user_id: UUID | None = None
    ) -> LessonResponse:
        """Get a lesson without requiring module_id (searches through modules)."""
        return await self.lesson_query.get_lesson_simplified(course_id, lesson_id, generate, user_id)

    async def generate_lesson(
        self, course_id: UUID, request: LessonCreate, user_id: UUID | None = None
    ) -> LessonResponse:
        """Generate a new lesson for a course."""
        return await self.lesson_creation.generate_lesson(course_id, request, user_id)

    async def regenerate_lesson(self, course_id: UUID, lesson_id: UUID, user_id: UUID | None = None) -> LessonResponse:
        """Regenerate an existing lesson."""
        return await self.lesson_creation.regenerate_lesson(course_id, lesson_id, user_id)

    async def update_lesson(
        self, course_id: UUID, lesson_id: UUID, request: LessonUpdate, user_id: UUID | None = None
    ) -> LessonResponse:
        """Update lesson metadata/content."""
        return await self.lesson_update.update_lesson(course_id, lesson_id, request, user_id)

    async def delete_lesson(self, course_id: UUID, lesson_id: UUID, user_id: UUID | None = None) -> bool:
        """Delete a lesson."""
        return await self.lesson_deletion.delete_lesson(course_id, lesson_id, user_id)

    # Progress tracking operations
    async def get_course_progress(self, course_id: UUID, user_id: UUID | None = None) -> CourseProgressResponse:
        """Get overall progress for a course."""
        return await self.progress_tracking.get_course_progress(course_id, user_id)

    async def update_lesson_status(
        self, course_id: UUID, module_id: UUID, lesson_id: UUID, request: LessonStatusUpdate, user_id: UUID | None = None
    ) -> LessonStatusResponse:
        """Update the status of a specific lesson."""
        return await self.progress_tracking.update_lesson_status(course_id, module_id, lesson_id, request, user_id)

    async def get_lesson_status(
        self, course_id: UUID, module_id: UUID, lesson_id: UUID, user_id: UUID | None = None
    ) -> LessonStatusResponse:
        """Get the status of a specific lesson."""
        return await self.progress_tracking.get_lesson_status(course_id, module_id, lesson_id, user_id)

    async def get_all_lesson_statuses(self, course_id: UUID, user_id: UUID | None = None) -> dict[str, str]:
        """Get all lesson statuses for a course."""
        return await self.progress_tracking.get_all_lesson_statuses(course_id, user_id)
