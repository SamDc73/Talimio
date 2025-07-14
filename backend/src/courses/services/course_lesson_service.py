"""Course lesson operations service.

Handles CRUD operations for lessons within course modules.
"""

import uuid
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.client import create_lesson_body
from src.courses.models import Node, Roadmap
from src.courses.schemas import (
    LessonCreate,
    LessonResponse,
    LessonUpdate,
)
from src.courses.services.lesson_dao import LessonDAO


class CourseLessonService:
    """Service for course lesson operations."""

    def __init__(self, session: AsyncSession, user_id: str | None = None) -> None:
        """Initialize the lesson service.

        Args:
            session: Database session
            user_id: User ID for user-specific operations
        """
        self.session = session
        self.user_id = user_id

    async def list_lessons(self, course_id: UUID, _user_id: str | None = None) -> list[LessonResponse]:
        """List all lessons for a course."""
        # Verify course exists
        course_query = select(Roadmap).where(Roadmap.id == course_id)
        result = await self.session.execute(course_query)
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

        # Get lessons for this course
        lesson_data_list = []
        conn = await LessonDAO.get_connection()
        try:
            rows = await conn.fetch(
                "SELECT * FROM lesson WHERE course_id = $1 ORDER BY created_at DESC", str(course_id)
            )
            lesson_data_list = [dict(row) for row in rows]
        finally:
            await conn.close()

        # Convert to CourseService response format
        return [
            LessonResponse(
                id=lesson_data["id"],
                course_id=course_id,
                slug=lesson_data["slug"],
                md_source=lesson_data["md_source"],
                html_cache=lesson_data.get("html_cache"),
                citations=lesson_data.get("citations") or [],
                created_at=lesson_data["created_at"],
                updated_at=lesson_data["updated_at"],
            )
            for lesson_data in lesson_data_list
        ]

    async def get_lesson(
        self,
        course_id: UUID,
        lesson_id: UUID,
        generate: bool = False,
        user_id: str | None = None,
        module_id: UUID | None = None,
    ) -> LessonResponse:
        """Get a specific lesson, optionally generating if missing."""
        try:
            # Try to get existing lesson
            lesson_data = await LessonDAO.get_by_id(lesson_id)
            if lesson_data:
                return LessonResponse(
                    id=lesson_data["id"],
                    course_id=course_id,
                    slug=lesson_data["slug"],
                    md_source=lesson_data["md_source"],
                    html_cache=lesson_data.get("html_cache"),
                    citations=lesson_data.get("citations") or [],
                    created_at=lesson_data["created_at"],
                    updated_at=lesson_data["updated_at"],
                )
            # Lesson not found, raise 404 to trigger generation if needed
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
        except HTTPException as e:
            if e.status_code == 404 and generate and module_id:
                # Generate lesson if it doesn't exist and generate=True
                return await self.generate_lesson(
                    course_id,
                    module_id,
                    LessonCreate(
                        slug=f"lesson-{str(lesson_id)[:8]}",
                        node_meta={
                            "lesson_id": str(lesson_id),
                            "course_id": str(course_id),
                            "module_id": str(module_id),
                        },
                    ),
                    user_id,
                )
            raise

    async def get_lesson_simplified(
        self, course_id: UUID, lesson_id: UUID, generate: bool = False, user_id: str | None = None
    ) -> LessonResponse:
        """Get a lesson without requiring module_id."""
        try:
            # Try to get existing lesson directly
            lesson_data = await LessonDAO.get_by_id(lesson_id)
            if lesson_data:
                # Find which module this lesson belongs to by checking all modules
                from src.courses.services.course_module_service import CourseModuleService

                module_service = CourseModuleService(self.session, user_id)
                modules = await module_service.list_modules(course_id, user_id)
                if not modules:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No modules found for course")

                # Use first module as fallback - lesson exists so module relationship isn't critical
                return LessonResponse(
                    id=lesson_data["id"],
                    course_id=course_id,
                    module_id=modules[0].id,
                    slug=lesson_data["slug"],
                    md_source=lesson_data["md_source"],
                    html_cache=lesson_data.get("html_cache"),
                    citations=lesson_data.get("citations") or [],
                    created_at=lesson_data["created_at"],
                    updated_at=lesson_data["updated_at"],
                )
            # Lesson not found, raise 404 to trigger generation if needed
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
        except HTTPException as e:
            if e.status_code == 404 and generate:
                # Generate lesson using first available module
                from src.courses.services.course_module_service import CourseModuleService

                module_service = CourseModuleService(self.session, user_id)
                modules = await module_service.list_modules(course_id, user_id)
                if not modules:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND, detail="No modules available for lesson generation"
                    ) from None

                return await self.get_lesson(course_id, lesson_id, generate, user_id, modules[0].id)
            raise

    async def generate_lesson(
        self, course_id: UUID, module_id: UUID, request: LessonCreate, _user_id: str | None = None
    ) -> LessonResponse:
        """Generate a new lesson for a module."""
        # Verify module exists and get roadmap info
        module_query = (
            select(Node, Roadmap)
            .join(Roadmap, Node.roadmap_id == Roadmap.id)
            .where(and_(Node.id == module_id, Node.roadmap_id == course_id))
        )
        result = await self.session.execute(module_query)
        row = result.one_or_none()

        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")

        module_node, roadmap = row

        # Get full course outline for context
        all_modules_query = select(Node).where(Node.roadmap_id == course_id).order_by(Node.order)
        modules_result = await self.session.execute(all_modules_query)
        all_modules = modules_result.scalars().all()

        # Build course outline context
        course_outline = []
        current_module_index = -1
        for i, module in enumerate(all_modules):
            course_outline.append(
                {
                    "title": module.title,
                    "description": module.description,
                    "order": module.order,
                    "is_current": module.id == module_id,
                }
            )
            if module.id == module_id:
                current_module_index = i

        # Extract lesson_id from the request if it exists
        lesson_id_str = request.node_meta.get("lesson_id")
        lesson_id = UUID(lesson_id_str) if lesson_id_str else None

        # Generate lesson content using AI with full course context
        lesson_context = {
            "title": module_node.title,
            "description": module_node.description,
            "content": module_node.content or "",
            "node_id": str(module_id),
            "roadmap_id": str(course_id),
            "skill_level": roadmap.skill_level,
            "course_outline": course_outline,
            "current_module_index": current_module_index,
            "total_modules": len(all_modules),
            "course_title": roadmap.title,
            "course_description": roadmap.description,
        }

        # Generate lesson body using AI
        lesson_content, citations = await create_lesson_body(lesson_context)

        # Create lesson data for database
        now = datetime.now(UTC)
        lesson_data = {
            "id": lesson_id or uuid.uuid4(),
            "course_id": str(course_id),  # Use actual course (roadmap) ID for foreign key
            "slug": request.slug,
            "md_source": lesson_content,
            "node_id": str(module_id),  # Store module ID in node_id field
            "html_cache": None,
            "created_at": now,
            "updated_at": now,
            "citations": citations,
        }

        # Save lesson to database
        saved_lesson = await LessonDAO.insert(lesson_data)

        return LessonResponse(
            id=saved_lesson["id"],
            course_id=course_id,
            module_id=module_id,
            slug=saved_lesson["slug"],
            md_source=saved_lesson["md_source"],
            html_cache=saved_lesson.get("html_cache"),
            citations=saved_lesson.get("citations") or [],
            created_at=saved_lesson["created_at"],
            updated_at=saved_lesson["updated_at"],
        )

    async def regenerate_lesson(
        self, course_id: UUID, module_id: UUID, lesson_id: UUID, _user_id: str | None = None
    ) -> LessonResponse:
        """Regenerate an existing lesson."""
        # Get existing lesson first
        existing_lesson = await self.get_lesson(course_id, module_id, lesson_id, generate=False, user_id=_user_id)

        # Generate new content with same slug
        new_lesson = await self.generate_lesson(
            course_id,
            module_id,
            LessonCreate(
                slug=existing_lesson.slug,
                node_meta={
                    "regenerated": True,
                    "original_lesson_id": str(lesson_id),
                    "course_id": str(course_id),
                    "module_id": str(module_id),
                },
            ),
            _user_id,
        )

        # Update the existing lesson with new content
        update_request = LessonUpdate(
            md_source=new_lesson.md_source,
            html_cache=None,  # Clear cache to force regeneration
        )

        return await self.update_lesson(course_id, module_id, lesson_id, update_request, _user_id)

    async def update_lesson(
        self, course_id: UUID, module_id: UUID, lesson_id: UUID, request: LessonUpdate, _user_id: str | None = None
    ) -> LessonResponse:
        """Update lesson metadata/content."""
        # Get update data
        update_data = request.model_dump(exclude_unset=True)
        update_data["updated_at"] = datetime.now(UTC)

        # Update using LessonDAO
        lesson_data = await LessonDAO.update(lesson_id, update_data)

        if not lesson_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

        return LessonResponse(
            id=lesson_data["id"],
            course_id=course_id,
            module_id=module_id,
            slug=lesson_data["slug"],
            md_source=lesson_data["md_source"],
            html_cache=lesson_data.get("html_cache"),
            citations=lesson_data.get("citations") or [],
            created_at=lesson_data["created_at"],
            updated_at=lesson_data["updated_at"],
        )

    async def delete_lesson(
        self, _course_id: UUID, _module_id: UUID, lesson_id: UUID, _user_id: str | None = None
    ) -> bool:
        """Delete a lesson."""
        # Verify lesson exists first
        lesson_data = await LessonDAO.get_by_id(lesson_id)
        if not lesson_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

        # Delete using LessonDAO
        return await LessonDAO.delete(lesson_id)
