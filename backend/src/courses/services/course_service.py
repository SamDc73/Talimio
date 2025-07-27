"""Refactored CourseService implementation using orchestrator pattern.

This is the new modular implementation that replaces the monolithic CourseService.
"""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.mode_aware_service import ModeAwareService

# UserContext removed - using UUID directly
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
from src.courses.services.course_orchestrator_service import CourseOrchestratorService
from src.courses.services.interface import ICourseService


class CourseService(ICourseService, ModeAwareService):
    """Refactored CourseService using modular architecture.

    This implementation uses the new modular service architecture under the hood.
    """

    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        """Initialize the course service.

        Args:
            session: Database session
            user_id: User ID for filtering courses
        """
        ModeAwareService.__init__(self)
        self.session = session
        self.user_id = user_id
        self._logger = logging.getLogger(__name__)
        self._orchestrator = CourseOrchestratorService(session, user_id)

    async def create_course(self, request: CourseCreate) -> CourseResponse:
        """Create a new course using AI generation."""
        self.log_access("create", self.user_id, "course")
        return await self._orchestrator.create_course(request, self.user_id)

    async def get_course(self, course_id: UUID) -> CourseResponse:
        """Get a specific course by ID."""
        self.log_access("get", self.user_id, "course", str(course_id))
        return await self._orchestrator.get_course(course_id, self.user_id)

    async def list_courses(
        self, page: int = 1, per_page: int = 20, search: str | None = None
    ) -> tuple[list[CourseResponse], int]:
        """List courses with pagination and optional search."""
        self.log_access("list", self.user_id, "course")
        return await self._orchestrator.list_courses(page, per_page, search, self.user_id)

    async def update_course(self, course_id: UUID, request: CourseUpdate) -> CourseResponse:
        """Update a course."""
        self.log_access("update", self.user_id, "course", str(course_id))
        return await self._orchestrator.update_course(course_id, request, self.user_id)

    async def delete_course(self, course_id: UUID) -> None:
        """Delete a course and all its associated data."""
        self.log_access("delete", self.user_id, "course", str(course_id))
        await self._orchestrator.delete_course(course_id, self.user_id)

    # Module operations
    async def list_modules(self, course_id: UUID) -> list[ModuleResponse]:
        """List all modules for a course."""
        self.log_access("list_modules", self.user_id, "course", str(course_id))
        return await self._orchestrator.list_modules(course_id, self.user_id)

    # Lesson operations
    async def list_lessons(self, course_id: UUID) -> list[LessonResponse]:
        """List all lessons for a course."""
        self.log_access("list_lessons", self.user_id, "course", str(course_id))
        return await self._orchestrator.list_lessons(course_id, self.user_id)

    async def get_lesson(
        self, course_id: UUID, lesson_id: UUID, generate: bool = False
    ) -> LessonResponse:
        """Get a specific lesson, optionally generating if missing."""
        self.log_access("get_lesson", self.user_id, "lesson", str(lesson_id))
        return await self._orchestrator.get_lesson(course_id, lesson_id, generate, self.user_id)

    async def get_lesson_simplified(
        self, course_id: UUID, lesson_id: UUID, generate: bool = False
    ) -> LessonResponse:
        """Get a lesson without requiring module_id (searches through modules)."""
        self.log_access("get_lesson_simplified", self.user_id, "lesson", str(lesson_id))
        return await self._orchestrator.get_lesson_simplified(course_id, lesson_id, generate, self.user_id)

    async def generate_lesson(
        self, course_id: UUID, request: LessonCreate
    ) -> LessonResponse:
        """Generate a new lesson for a course."""
        self.log_access("generate_lesson", self.user_id, "lesson")
        return await self._orchestrator.generate_lesson(course_id, request, self.user_id)

    async def regenerate_lesson(self, course_id: UUID, lesson_id: UUID) -> LessonResponse:
        """Regenerate an existing lesson."""
        self.log_access("regenerate_lesson", self.user_id, "lesson", str(lesson_id))
        return await self._orchestrator.regenerate_lesson(course_id, lesson_id, self.user_id)

    async def update_lesson(
        self, course_id: UUID, lesson_id: UUID, request: LessonUpdate
    ) -> LessonResponse:
        """Update lesson metadata/content."""
        self.log_access("update_lesson", self.user_id, "lesson", str(lesson_id))
        return await self._orchestrator.update_lesson(course_id, lesson_id, request, self.user_id)

    async def delete_lesson(self, course_id: UUID, lesson_id: UUID) -> bool:
        """Delete a lesson."""
        self.log_access("delete_lesson", self.user_id, "lesson", str(lesson_id))
        return await self._orchestrator.delete_lesson(course_id, lesson_id, self.user_id)

    # Progress tracking operations
    async def get_course_progress(self, course_id: UUID) -> CourseProgressResponse:
        """Get overall progress for a course."""
        self.log_access("get_progress", self.user_id, "course", str(course_id))
        return await self._orchestrator.get_course_progress(course_id, self.user_id)

    async def update_lesson_status(
        self, course_id: UUID, module_id: UUID, lesson_id: UUID, request: LessonStatusUpdate
    ) -> LessonStatusResponse:
        """Update the status of a specific lesson."""
        self.log_access("update_lesson_status", self.user_id, "lesson", str(lesson_id))
        return await self._orchestrator.update_lesson_status(course_id, module_id, lesson_id, request, self.user_id)

    async def get_lesson_status(
        self, course_id: UUID, module_id: UUID, lesson_id: UUID
    ) -> LessonStatusResponse:
        """Get the status of a specific lesson."""
        self.log_access("get_lesson_status", self.user_id, "lesson", str(lesson_id))
        return await self._orchestrator.get_lesson_status(course_id, module_id, lesson_id, self.user_id)

    async def get_all_lesson_statuses(self, course_id: UUID) -> dict[str, str]:
        """Get all lesson statuses for a course."""
        self.log_access("get_all_lesson_statuses", self.user_id, "course", str(course_id))
        return await self._orchestrator.get_all_lesson_statuses(course_id, self.user_id)
