"""Interface definition for CourseService using Protocol for type checking."""

from typing import Protocol
from uuid import UUID

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


class ICourseService(Protocol):
    """Interface for unified course service operations.

    This interface defines all the operations that should be supported
    by any course service implementation, allowing for easy testing
    and migration between different implementations.
    """

    # Course operations
    async def create_course(self, request: CourseCreate, user_id: str | None = None) -> CourseResponse:
        """Create a new course using AI generation."""
        ...

    async def get_course(self, course_id: UUID, user_id: str | None = None) -> CourseResponse:
        """Get a specific course by ID."""
        ...

    async def list_courses(
        self, page: int = 1, per_page: int = 20, search: str | None = None, user_id: str | None = None
    ) -> tuple[list[CourseResponse], int]:
        """List courses with pagination and optional search."""
        ...

    async def update_course(self, course_id: UUID, request: CourseUpdate, user_id: str | None = None) -> CourseResponse:
        """Update a course."""
        ...

    async def delete_course(self, course_id: UUID, user_id: str | None = None) -> None:
        """Delete a course and all its associated data."""
        ...

    # Lesson operations
    async def list_lessons(self, course_id: UUID, user_id: str | None = None) -> list[LessonResponse]:
        """List all lessons for a course."""
        ...

    async def get_lesson(
        self, course_id: UUID, lesson_id: UUID, generate: bool = False, user_id: str | None = None
    ) -> LessonResponse:
        """Get a specific lesson, optionally generating if missing."""
        ...

    async def get_lesson_simplified(
        self, course_id: UUID, lesson_id: UUID, generate: bool = False, user_id: str | None = None
    ) -> LessonResponse:
        """Get a lesson without requiring module_id (searches through modules)."""
        ...

    async def generate_lesson(
        self, course_id: UUID, request: LessonCreate, user_id: str | None = None
    ) -> LessonResponse:
        """Generate a new lesson for a course."""
        ...

    async def regenerate_lesson(self, course_id: UUID, lesson_id: UUID, user_id: str | None = None) -> LessonResponse:
        """Regenerate an existing lesson."""
        ...

    async def update_lesson(
        self, course_id: UUID, lesson_id: UUID, request: LessonUpdate, user_id: str | None = None
    ) -> LessonResponse:
        """Update lesson metadata/content."""
        ...

    async def delete_lesson(self, course_id: UUID, lesson_id: UUID, user_id: str | None = None) -> bool:
        """Delete a lesson."""
        ...

    # Progress tracking operations
    async def get_course_progress(self, course_id: UUID, user_id: str | None = None) -> CourseProgressResponse:
        """Get overall progress for a course."""
        ...

    async def update_lesson_status(
        self, course_id: UUID, module_id: UUID, lesson_id: UUID, request: LessonStatusUpdate, user_id: str | None = None
    ) -> LessonStatusResponse:
        """Update the status of a specific lesson."""
        ...

    async def get_lesson_status(
        self, course_id: UUID, module_id: UUID, lesson_id: UUID, user_id: str | None = None
    ) -> LessonStatusResponse:
        """Get the status of a specific lesson."""
        ...
