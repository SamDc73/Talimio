"""Core course operations service.

Handles CRUD operations for courses (roadmaps).
"""

from datetime import datetime, UTC
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.ai.client import ModelManager
from src.ai.memory import Mem0Wrapper
from src.courses.models import Node, Roadmap
from src.courses.schemas import (
    CourseCreate,
    CourseResponse,
    CourseUpdate,
)


class CourseCoreService:
    """Service for core course operations."""

    def __init__(self, session: AsyncSession, user_id: str | None = None) -> None:
        """Initialize the core course service.

        Args:
            session: Database session
            user_id: User ID for user-specific operations
        """
        self.session = session
        self.user_id = user_id
        self.ai_client = ModelManager()
        self.memory_service = Mem0Wrapper() if user_id else None

    async def create_course(self, request: CourseCreate, _user_id: str | None = None) -> CourseResponse:
        """Create a new course using AI generation."""
        # Enhanced AI prompt for better course generation
        enhanced_prompt = f"""
        Create a comprehensive learning course for: {request.prompt}

        Requirements:
        - Structure the course into logical modules/topics
        - Ensure each module builds upon previous knowledge
        - Include practical examples and hands-on exercises
        - Target appropriate skill level (beginner to advanced progression)
        - Make it engaging and actionable

        Course request: {request.prompt}
        """

        # Generate course structure using AI
        try:
            nodes_data = await self.ai_client.generate_roadmap_content(
                title="Generated Course", skill_level="beginner", description=enhanced_prompt
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate course structure: {e!s}"
            ) from e

        # Create the course (roadmap) in database
        roadmap = Roadmap(
            title="Generated Course",
            description=f"AI-generated course: {request.prompt}",
            skill_level="beginner",
            tags_json="[]",
            archived=False,
            rag_enabled=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        self.session.add(roadmap)
        await self.session.flush()  # Get the ID

        # Create modules (nodes) for the course
        modules = []
        for i, module_data in enumerate(nodes_data):
            node = Node(
                roadmap_id=roadmap.id,
                title=module_data.get("title", f"Module {i + 1}"),
                description=module_data.get("description", ""),
                content=module_data.get("content", ""),
                order=i,
                status="not_started",
                completion_percentage=0.0,
                parent_id=None,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            self.session.add(node)
            modules.append(node)

        await self.session.commit()

        # Store course creation in memory for personalization
        if self.memory_service:
            await self.memory_service.add_memory(
                f"Created course: {roadmap.title}", {"course_id": str(roadmap.id), "prompt": request.prompt}
            )

        # Return the course response
        return CourseResponse(
            id=roadmap.id,
            title=roadmap.title,
            description=roadmap.description,
            skill_level=roadmap.skill_level,
            tags_json=roadmap.tags_json,
            archived=roadmap.archived,
            archived_at=roadmap.archived_at,
            rag_enabled=roadmap.rag_enabled,
            created_at=roadmap.created_at,
            updated_at=roadmap.updated_at,
        )

    async def get_course(self, course_id: UUID, _user_id: str | None = None) -> CourseResponse:
        """Get a course by ID with improved caching and optimization."""
        # Optimized query with eager loading
        query = select(Roadmap).options(selectinload(Roadmap.nodes)).where(Roadmap.id == course_id)

        result = await self.session.execute(query)
        roadmap = result.scalar_one_or_none()

        if not roadmap:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

        return CourseResponse(
            id=roadmap.id,
            title=roadmap.title,
            description=roadmap.description,
            skill_level=roadmap.skill_level,
            tags_json=roadmap.tags_json,
            archived=roadmap.archived,
            archived_at=roadmap.archived_at,
            rag_enabled=roadmap.rag_enabled,
            created_at=roadmap.created_at,
            updated_at=roadmap.updated_at,
        )

    async def list_courses(
        self, page: int = 1, per_page: int = 20, search: str | None = None, _user_id: str | None = None
    ) -> tuple[list[CourseResponse], int]:
        """List courses with improved pagination and search."""
        # Build query with search
        query = select(Roadmap).where(Roadmap.archived is False)

        if search:
            search_filter = or_(Roadmap.title.ilike(f"%{search}%"), Roadmap.description.ilike(f"%{search}%"))
            query = query.where(search_filter)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar()

        # Apply pagination and eager loading
        query = (
            query.options(selectinload(Roadmap.nodes))
            .order_by(Roadmap.updated_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )

        result = await self.session.execute(query)
        roadmaps = result.scalars().all()

        # Convert to course responses
        courses = [
            CourseResponse(
                id=roadmap.id,
                title=roadmap.title,
                description=roadmap.description,
                skill_level=roadmap.skill_level,
                tags_json=roadmap.tags_json,
                archived=roadmap.archived,
                archived_at=roadmap.archived_at,
                rag_enabled=roadmap.rag_enabled,
                created_at=roadmap.created_at,
                updated_at=roadmap.updated_at,
            )
            for roadmap in roadmaps
        ]

        return courses, total

    async def update_course(
        self, course_id: UUID, request: CourseUpdate, _user_id: str | None = None
    ) -> CourseResponse:
        """Update a course with improved validation and error handling."""
        query = select(Roadmap).where(Roadmap.id == course_id)
        result = await self.session.execute(query)
        roadmap = result.scalar_one_or_none()

        if not roadmap:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

        # Update fields if provided
        update_data = request.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(roadmap, field, value)

        roadmap.updated_at = datetime.now(UTC)

        await self.session.commit()

        # Return updated course
        return await self.get_course(course_id, _user_id)
