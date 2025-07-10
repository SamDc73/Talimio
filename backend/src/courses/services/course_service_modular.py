"""Modular CourseService implementation.

This implementation composes the specialized service classes to provide
the same interface as the original CourseService while maintaining
better separation of concerns.
"""

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
)
from src.courses.services.course_core_service import CourseCoreService
from src.courses.services.course_lesson_service import CourseLessonService
from src.courses.services.course_progress_service import CourseProgressService
from src.courses.services.interface import ICourseService


class CourseServiceModular(ICourseService):
    """Modular implementation of the CourseService interface.

    This implementation delegates to specialized service classes for better
    separation of concerns while maintaining the same public interface.
    """

    def __init__(self, session: AsyncSession, user_id: str | None = None) -> None:
        """Initialize the modular course service.

        Args:
            session: Database session
            user_id: User ID for user-specific operations
        """
        self.session = session
        self.user_id = user_id

        # Initialize specialized services
        self._core_service = CourseCoreService(session, user_id)
        self._lesson_service = CourseLessonService(session, user_id)
        self._progress_service = CourseProgressService(session, user_id)

    # Course operations - delegate to core service
    async def create_course(self, request: CourseCreate, user_id: str | None = None) -> CourseResponse:
        """Create a new course using AI generation."""
        return await self._core_service.create_course(request, user_id)

    async def get_course(self, course_id: UUID, user_id: str | None = None) -> CourseResponse:
        """Get a course by ID with improved caching and optimization."""
        return await self._core_service.get_course(course_id, user_id)

    async def list_courses(
        self, page: int = 1, per_page: int = 20, search: str | None = None, user_id: str | None = None
    ) -> tuple[list[CourseResponse], int]:
        """List courses with improved pagination and search."""
        return await self._core_service.list_courses(page, per_page, search, user_id)

    async def update_course(self, course_id: UUID, request: CourseUpdate, user_id: str | None = None) -> CourseResponse:
        """Update a course with improved validation and error handling."""
        return await self._core_service.update_course(course_id, request, user_id)

    # Lesson operations - delegate to lesson service
    async def list_lessons(self, course_id: UUID, user_id: str | None = None) -> list[LessonResponse]:
        """List all lessons for a course."""
        return await self._lesson_service.list_lessons(course_id, user_id)

    async def get_lesson(
        self, course_id: UUID, lesson_id: UUID, generate: bool = False, user_id: str | None = None
    ) -> LessonResponse:
        """Get a specific lesson, optionally generating if missing."""
        return await self._lesson_service.get_lesson(course_id, lesson_id, generate, user_id)

    async def get_lesson_simplified(
        self, course_id: UUID, lesson_id: UUID, generate: bool = False, user_id: str | None = None
    ) -> LessonResponse:
        """Get a lesson without requiring module_id."""
        return await self._lesson_service.get_lesson_simplified(course_id, lesson_id, generate, user_id)

    async def generate_lesson(
        self, course_id: UUID, module_id: UUID, request: LessonCreate, user_id: str | None = None
    ) -> LessonResponse:
        """Generate a new lesson for a module."""
        return await self._lesson_service.generate_lesson(course_id, module_id, request, user_id)

    async def regenerate_lesson(
        self, course_id: UUID, module_id: UUID, lesson_id: UUID, user_id: str | None = None
    ) -> LessonResponse:
        """Regenerate an existing lesson."""
        return await self._lesson_service.regenerate_lesson(course_id, module_id, lesson_id, user_id)

    async def update_lesson(
        self, course_id: UUID, module_id: UUID, lesson_id: UUID, request: LessonUpdate, user_id: str | None = None
    ) -> LessonResponse:
        """Update lesson metadata/content."""
        return await self._lesson_service.update_lesson(course_id, module_id, lesson_id, request, user_id)

    async def delete_lesson(
        self, course_id: UUID, module_id: UUID, lesson_id: UUID, user_id: str | None = None
    ) -> bool:
        """Delete a lesson."""
        return await self._lesson_service.delete_lesson(course_id, module_id, lesson_id, user_id)

    # Progress operations - delegate to progress service
    async def get_course_progress(self, course_id: UUID, user_id: str | None = None) -> CourseProgressResponse:
        """Get overall progress for a course."""
        return await self._progress_service.get_course_progress(course_id, user_id)

    async def update_lesson_status(
        self, course_id: UUID, module_id: UUID, lesson_id: UUID, request: LessonStatusUpdate, user_id: str | None = None
    ) -> LessonStatusResponse:
        """Update the status of a specific lesson."""
        return await self._progress_service.update_lesson_status(course_id, module_id, lesson_id, request, user_id)

    async def get_lesson_status(
        self, course_id: UUID, module_id: UUID, lesson_id: UUID, user_id: str | None = None
    ) -> LessonStatusResponse:
        """Get the status of a specific lesson."""
        return await self._progress_service.get_lesson_status(course_id, module_id, lesson_id, user_id)
