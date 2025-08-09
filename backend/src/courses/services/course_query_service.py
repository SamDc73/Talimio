"""Course query service for read operations on courses."""

import logging
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.courses.models import Node, Roadmap
from src.courses.schemas import CourseResponse, ModuleResponse
from src.courses.services.course_response_builder import CourseResponseBuilder


class CourseQueryService:
    """Service for querying course data."""

    def __init__(self, session: AsyncSession, user_id: UUID | None = None) -> None:
        """Initialize the course query service.

        Args:
            session: Database session
            user_id: User ID for user-specific operations
        """
        self.session = session
        self.user_id = user_id
        self.response_builder = CourseResponseBuilder(session)
        self._logger = logging.getLogger(__name__)

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
        # Get effective user_id
        effective_user_id = user_id or self.user_id

        # Get the roadmap/course with user filtering
        query = select(Roadmap).where(Roadmap.id == course_id, Roadmap.user_id == effective_user_id)

        result = await self.session.execute(query)
        roadmap = result.scalar_one_or_none()

        if not roadmap:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

        # Get modules and lessons
        modules_query = (
            select(Node)
            .where(
                Node.roadmap_id == course_id,
                Node.parent_id.is_(None),  # Modules have no parent
            )
            .order_by(Node.order)
        )

        modules_result = await self.session.execute(modules_query)
        modules = modules_result.scalars().all()

        modules_data = []
        for module in modules:
            module_response = await self.response_builder.build_module_response(module, course_id)
            modules_data.append(module_response)

        return self.response_builder.build_course_response_from_roadmap(roadmap, modules_data)

    async def list_courses(
        self, page: int = 1, per_page: int = 20, search: str | None = None, user_id: UUID | None = None
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
        offset = (page - 1) * per_page

        # Get effective user_id
        effective_user_id = user_id or self.user_id

        # Build query with user filtering
        query = select(Roadmap).where(Roadmap.user_id == effective_user_id)
        count_query = select(func.count(Roadmap.id)).where(Roadmap.user_id == effective_user_id)

        if search:
            search_filter = or_(Roadmap.title.ilike(f"%{search}%"), Roadmap.description.ilike(f"%{search}%"))
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        # Get total count
        count_result = await self.session.execute(count_query)
        total = count_result.scalar()

        # Get paginated results
        query = query.order_by(Roadmap.created_at.desc()).offset(offset).limit(per_page)
        result = await self.session.execute(query)
        roadmaps = result.scalars().all()

        # Convert to responses (simplified, without modules for list view)
        courses = [
            self.response_builder.build_course_response_from_roadmap(
                roadmap,
                [],  # Empty modules for list view
            )
            for roadmap in roadmaps
        ]

        return courses, total

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
        # Get effective user_id
        effective_user_id = user_id or self.user_id

        # Verify course exists and user has access
        course_query = select(Roadmap).where(Roadmap.id == course_id, Roadmap.user_id == effective_user_id)

        course_result = await self.session.execute(course_query)
        if not course_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

        # Get modules
        modules_query = (
            select(Node)
            .where(
                Node.roadmap_id == course_id,
                Node.parent_id.is_(None),  # Modules have no parent
            )
            .order_by(Node.order)
        )

        modules_result = await self.session.execute(modules_query)
        modules = modules_result.scalars().all()

        return [self.response_builder.build_module_response_simple(module, course_id) for module in modules]
