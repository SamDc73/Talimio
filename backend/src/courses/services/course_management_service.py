"""Refactored course management service that delegates to specialized services."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.courses.schemas import CourseCreate, CourseResponse, CourseUpdate, ModuleResponse
from src.courses.services.course_creation_service import CourseCreationService
from src.courses.services.course_query_service import CourseQueryService
from src.courses.services.course_update_service import CourseUpdateService


class CourseManagementService:
    """Service for managing course CRUD operations - refactored version."""

    def __init__(self, session: AsyncSession, user_id: UUID | None = None) -> None:
        """Initialize the course management service.

        Args:
            session: Database session
            user_id: User ID for user-specific operations
        """
        self.session = session
        self.user_id = user_id

        # Initialize specialized services
        self.creation_service = CourseCreationService(session, user_id)
        self.query_service = CourseQueryService(session, user_id)
        self.update_service = CourseUpdateService(session, user_id)

    async def create_course(self, request: CourseCreate, user_id: UUID | None = None) -> CourseResponse:
        """Create a new course using AI generation.

        Args:
            request: Course creation request
            user_id: User ID (optional override)

        Returns
        -------
            Created course response

        Raises
        ------
            HTTPException: If course creation fails
        """
        return await self.creation_service.create_course(request, user_id)

    async def get_course(self, course_id: UUID, user_id: UUID | None = None) -> CourseResponse:
        """Get a specific course by ID.

        Args:
            course_id: Course ID
            user_id: User ID (optional override)

        Returns
        -------
            Course response

        Raises
        ------
            HTTPException: If course not found
        """
        return await self.query_service.get_course(course_id, user_id)

    async def list_courses(
        self,
        page: int = 1,
        per_page: int = 20,
        search: str | None = None,
        user_id: UUID | None = None
    ) -> tuple[list[CourseResponse], int]:
        """List courses with pagination and optional search.

        Args:
            page: Page number (1-based)
            per_page: Items per page
            search: Optional search term
            user_id: User ID (optional override)

        Returns
        -------
            Tuple of (courses list, total count)
        """
        return await self.query_service.list_courses(page, per_page, search, user_id)

    async def update_course(
        self,
        course_id: UUID,
        request: CourseUpdate,
        user_id: UUID | None = None
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
        return await self.update_service.update_course(course_id, request, user_id)

    async def list_modules(self, course_id: UUID, user_id: UUID | None = None) -> list[ModuleResponse]:
        """List all modules for a course.

        Args:
            course_id: Course ID
            user_id: User ID (optional override)

        Returns
        -------
            List of module responses

        Raises
        ------
            HTTPException: If course not found
        """
        return await self.query_service.list_modules(course_id, user_id)

    async def delete_course(self, course_id: UUID, user_id: UUID | None = None) -> None:
        """Delete a course.

        Args:
            course_id: Course ID
            user_id: User ID (optional override)

        Raises
        ------
            HTTPException: If course not found or deletion fails
        """
        from sqlalchemy import delete

        from src.courses.models import Course, CourseModule, Lesson, LessonProgress

        # Check if course exists using query service
        try:
            course = await self.query_service.get_course(course_id, user_id)
        except Exception:
            error_msg = f"Course with ID {course_id} not found"
            raise ValueError(error_msg)

        # Delete related records first to avoid foreign key constraints
        # 1. Delete progress records (uses string course_id/module_id)
        await self.session.execute(
            delete(LessonProgress).where(LessonProgress.course_id == str(course_id))
        )

        # 2. Delete lessons
        await self.session.execute(
            delete(Lesson).where(Lesson.roadmap_id == course_id)
        )

        # 3. Delete modules/nodes
        await self.session.execute(
            delete(CourseModule).where(CourseModule.roadmap_id == course_id)
        )

        # 4. Finally delete the course (documents should cascade)
        await self.session.execute(delete(Course).where(Course.id == course_id))
        await self.session.commit()
