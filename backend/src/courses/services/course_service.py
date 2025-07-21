"""Refactored CourseService implementation using orchestrator pattern.

This is the new modular implementation that replaces the monolithic CourseService.
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
from src.courses.services.course_orchestrator_service import CourseOrchestratorService
from src.courses.services.interface import ICourseService


class CourseService(ICourseService):
    """Refactored CourseService using modular architecture.

    This implementation uses the new modular service architecture under the hood.
    """

    def __init__(self, session: AsyncSession, user_id: str | None = None) -> None:
        """Initialize the course service.

        Args:
            session: Database session
            user_id: User ID for user-specific operations
        """
        self.session = session
        self.user_id = user_id
        self._logger = logging.getLogger(__name__)
        self._orchestrator = CourseOrchestratorService(session, user_id)

    async def create_course(self, request: CourseCreate, user_id: str | None = None) -> CourseResponse:
        """Create a new course using AI generation."""
        return await self._orchestrator.create_course(request, user_id)

    async def get_course(self, course_id: UUID, user_id: str | None = None) -> CourseResponse:
        """Get a specific course by ID."""
        return await self._orchestrator.get_course(course_id, user_id)

    async def list_courses(
        self, page: int = 1, per_page: int = 20, search: str | None = None, user_id: str | None = None
    ) -> tuple[list[CourseResponse], int]:
        """List courses with pagination and optional search."""
        return await self._orchestrator.list_courses(page, per_page, search, user_id)

    async def update_course(self, course_id: UUID, request: CourseUpdate, user_id: str | None = None) -> CourseResponse:
        """Update a course."""
        return await self._orchestrator.update_course(course_id, request, user_id)

    async def delete_course(self, course_id: UUID, user_id: str | None = None) -> None:
        """Delete a course and all its associated data."""
        await self._orchestrator.delete_course(course_id, user_id)

    # Module operations
    async def list_modules(self, course_id: UUID, user_id: str | None = None) -> list[ModuleResponse]:
        """List all modules for a course."""
        return await self._orchestrator.list_modules(course_id, user_id)

    # Lesson operations
    async def list_lessons(self, course_id: UUID, user_id: str | None = None) -> list[LessonResponse]:
        """List all lessons for a course."""
        return await self._orchestrator.list_lessons(course_id, user_id)

    async def get_lesson(
        self, course_id: UUID, lesson_id: UUID, generate: bool = False, user_id: str | None = None
    ) -> LessonResponse:
        """Get a specific lesson, optionally generating if missing."""
        return await self._orchestrator.get_lesson(course_id, lesson_id, generate, user_id)

    async def get_lesson_simplified(
        self, course_id: UUID, lesson_id: UUID, generate: bool = False, user_id: str | None = None
    ) -> LessonResponse:
        """Get a lesson without requiring module_id (searches through modules)."""
        return await self._orchestrator.get_lesson_simplified(course_id, lesson_id, generate, user_id)

    async def generate_lesson(
        self, course_id: UUID, request: LessonCreate, user_id: str | None = None
    ) -> LessonResponse:
        """Generate a new lesson for a course."""
        return await self._orchestrator.generate_lesson(course_id, request, user_id)

    async def regenerate_lesson(self, course_id: UUID, lesson_id: UUID, user_id: str | None = None) -> LessonResponse:
        """Regenerate an existing lesson."""
        return await self._orchestrator.regenerate_lesson(course_id, lesson_id, user_id)

    async def update_lesson(
        self, course_id: UUID, lesson_id: UUID, request: LessonUpdate, user_id: str | None = None
    ) -> LessonResponse:
        """Update lesson metadata/content."""
        return await self._orchestrator.update_lesson(course_id, lesson_id, request, user_id)

    async def delete_lesson(self, course_id: UUID, lesson_id: UUID, user_id: str | None = None) -> bool:
        """Delete a lesson."""
        return await self._orchestrator.delete_lesson(course_id, lesson_id, user_id)

    # Progress tracking operations
    async def get_course_progress(self, course_id: UUID, user_id: str | None = None) -> CourseProgressResponse:
        """Get overall progress for a course."""
        return await self._orchestrator.get_course_progress(course_id, user_id)

    async def update_lesson_status(
        self, course_id: UUID, module_id: UUID, lesson_id: UUID, request: LessonStatusUpdate, user_id: str | None = None
    ) -> LessonStatusResponse:
        """Update the status of a specific lesson."""
        return await self._orchestrator.update_lesson_status(course_id, module_id, lesson_id, request, user_id)

    async def get_lesson_status(
        self, course_id: UUID, module_id: UUID, lesson_id: UUID, user_id: str | None = None
    ) -> LessonStatusResponse:
        """Get the status of a specific lesson."""
        return await self._orchestrator.get_lesson_status(course_id, module_id, lesson_id, user_id)

    async def get_all_lesson_statuses(self, course_id: UUID, user_id: str | None = None) -> dict[str, str]:
        """Get all lesson statuses for a course."""
        return await self._orchestrator.get_all_lesson_statuses(course_id, user_id)
