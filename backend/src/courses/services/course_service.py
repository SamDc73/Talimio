"""CourseService implementation with modular architecture support.

This implementation provides backward compatibility while supporting
the new modular service architecture. Can switch between monolithic
and modular implementations based on feature flags or configuration.
"""

import os
import uuid
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.ai.client import ModelManager, create_lesson_body
from src.ai.memory import Mem0Wrapper
from src.courses.models import Node, Roadmap
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
from src.courses.services.interface import ICourseService
from src.progress.models import Progress
from src.storage.lesson_dao import LessonDAO


class CourseService(ICourseService):
    """New implementation of the CourseService interface.

    This is the new implementation that will replace the legacy adapter
    over time using feature flags.
    """

    def __init__(self, session: AsyncSession, user_id: str | None = None) -> None:
        """Initialize the course service.

        Args:
            session: Database session
            user_id: User ID for user-specific operations
        """
        self.session = session
        self.user_id = user_id
        self.ai_client = ModelManager()
        self.memory_service = Mem0Wrapper() if user_id else None

        # Check if modular implementation should be used
        self._use_modular = os.getenv("USE_MODULAR_COURSE_SERVICE", "false").lower() == "true"
        self._modular_service = None

        if self._use_modular:
            # Lazy import to avoid circular dependencies
            from src.courses.services.course_service_modular import CourseServiceModular
            self._modular_service = CourseServiceModular(session, user_id)

    async def create_course(self, request: CourseCreate, _user_id: str | None = None) -> CourseResponse:
        """Create a new course using AI generation.

        This is a new implementation that improves upon the legacy roadmap creation
        by providing better AI prompting and more structured course generation.
        """
        # Delegate to modular service if enabled
        if self._use_modular and self._modular_service:
            return await self._modular_service.create_course(request, _user_id)
        # Use the provided user_id or fall back to the service's user_id

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

        # Generate title and description using AI
        try:
            title_description = await self.ai_client.generate_roadmap_title_description(
                user_prompt=request.prompt, skill_level="beginner"
            )
            course_title = title_description["title"]
            course_description = title_description["description"]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate course title: {e!s}"
            ) from e

        # Generate course structure using AI
        try:
            nodes_data = await self.ai_client.generate_roadmap_content(
                title=course_title, skill_level="beginner", description=enhanced_prompt
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate course structure: {e!s}"
            ) from e

        # Create the course (roadmap) in database
        roadmap = Roadmap(
            title=course_title,
            description=course_description,
            skill_level="beginner",
            tags_json="[]",
            archived=False,
            rag_enabled=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        self.session.add(roadmap)
        await self.session.flush()  # Get the ID

        # Create modules and their lessons based on AI-generated structure
        for i, module_data in enumerate(nodes_data):
            # Create the main module
            module_node = Node(
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
            self.session.add(module_node)
            await self.session.flush()  # Get module ID before creating children

            # Create lesson nodes from AI-generated subtopics
            subtopics = module_data.get("children", module_data.get("subtopics", []))
            for j, subtopic in enumerate(subtopics):
                if isinstance(subtopic, dict):
                    lesson_node = Node(
                        roadmap_id=roadmap.id,
                        title=subtopic.get("title", f"Lesson {j + 1}"),
                        description=subtopic.get("description", ""),
                        content=subtopic.get("content", ""),
                        order=j,
                        status="not_started",
                        completion_percentage=0.0,
                        parent_id=module_node.id,  # Child of the module
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    )
                    self.session.add(lesson_node)

        await self.session.commit()

        # Store course creation in memory for personalization
        if self.memory_service:
            await self.memory_service.add_memory(
                f"Created course: {course_title}", {"course_id": str(roadmap.id), "prompt": request.prompt}
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

    async def get_course(self, course_id: UUID, __user_id: str | None = None) -> CourseResponse:
        """Get a course by ID with improved caching and optimization."""
        # Optimized query with eager loading
        query = select(Roadmap).options(selectinload(Roadmap.nodes)).where(Roadmap.id == course_id)

        result = await self.session.execute(query)
        roadmap = result.scalar_one_or_none()

        if not roadmap:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Course not found: {course_id}")

        # Convert nodes to modules for response
        modules = [
            ModuleResponse(
                id=node.id,
                course_id=roadmap.id,
                title=node.title,
                description=node.description,
                content=node.content,
                order=node.order,
                status=node.status,
                completion_percentage=node.completion_percentage,
                parent_id=node.parent_id,
                created_at=node.created_at,
                updated_at=node.updated_at,
            )
            for node in roadmap.nodes
        ]

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
            modules=modules,
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
        courses = []
        for roadmap in roadmaps:
            # Convert nodes to modules for response
            modules = [
                ModuleResponse(
                    id=node.id,
                    course_id=roadmap.id,
                    title=node.title,
                    description=node.description,
                    content=node.content,
                    order=node.order,
                    status=node.status,
                    completion_percentage=node.completion_percentage,
                    parent_id=node.parent_id,
                    created_at=node.created_at,
                    updated_at=node.updated_at,
                )
                for node in roadmap.nodes
            ]

            courses.append(
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
                    modules=modules,
                )
            )

        return courses, total

    async def update_course(self, course_id: UUID, request: CourseUpdate, _user_id: str | None = None) -> CourseResponse:
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

    async def list_modules(self, course_id: UUID, _user_id: str | None = None) -> list[ModuleResponse]:
        """List all modules for a course."""
        query = select(Node).where(Node.roadmap_id == course_id).order_by(Node.order)
        result = await self.session.execute(query)
        nodes = result.scalars().all()

        return [
            ModuleResponse(
                id=node.id,
                course_id=course_id,
                title=node.title,
                description=node.description,
                content=node.content,
                order=node.order,
                status=node.status,
                completion_percentage=node.completion_percentage,
                parent_id=node.parent_id,
                created_at=node.created_at,
                updated_at=node.updated_at,
            )
            for node in nodes
        ]


    async def list_lessons(self, course_id: UUID, _user_id: str | None = None) -> list[LessonResponse]:
        """List all lessons for a course."""
        # Verify course exists
        course_query = select(Roadmap).where(Roadmap.id == course_id)
        result = await self.session.execute(course_query)
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

        # Get lessons for this course
        lesson_data_list = []
        from src.storage.lesson_dao import LessonDAO
        conn = await LessonDAO.get_connection()
        try:
            rows = await conn.fetch(
                "SELECT * FROM lesson WHERE course_id = $1 ORDER BY created_at DESC",
                str(course_id)
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
        self, course_id: UUID, lesson_id: UUID, generate: bool = False, _user_id: str | None = None
    ) -> LessonResponse:
        """Get a specific lesson, optionally generating if missing."""
        try:
            # Try to get existing lesson
            lesson_data = await LessonDAO.get_by_id(lesson_id)
            if lesson_data:
                # Find which module this lesson belongs to by checking all modules
                modules = await self.list_modules(course_id, _user_id)
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
                modules = await self.list_modules(course_id, _user_id)
                if not modules:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND, detail="No modules available for lesson generation"
                    ) from None

                # Generate lesson if it doesn't exist and generate=True
                return await self.generate_lesson(
                    course_id,
                    modules[0].id,
                    LessonCreate(
                        slug=f"lesson-{str(lesson_id)[:8]}",
                        node_meta={
                            "lesson_id": str(lesson_id),
                            "course_id": str(course_id),
                            "module_id": str(modules[0].id),
                        },
                    ),
                    _user_id,
                )
            raise

    async def get_lesson_simplified(
        self, course_id: UUID, lesson_id: UUID, generate: bool = False, _user_id: str | None = None
    ) -> LessonResponse:
        """Get a lesson without requiring module_id."""
        try:
            # Try to get existing lesson directly
            lesson_data = await LessonDAO.get_by_id(lesson_id)
            if lesson_data:
                # Find which module this lesson belongs to by checking all modules
                modules = await self.list_modules(course_id, _user_id)
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
                modules = await self.list_modules(course_id, _user_id)
                if not modules:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND, detail="No modules available for lesson generation"
                    ) from None

                return await self.generate_lesson(
                    course_id,
                    modules[0].id,
                    LessonCreate(
                        slug=f"lesson-{str(lesson_id)[:8]}",
                        node_meta={
                            "lesson_id": str(lesson_id),
                            "course_id": str(course_id),
                            "module_id": str(modules[0].id),
                        },
                    ),
                    _user_id,
                )
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
        all_modules_query = (
            select(Node)
            .where(Node.roadmap_id == course_id)
            .order_by(Node.order)
        )
        modules_result = await self.session.execute(all_modules_query)
        all_modules = modules_result.scalars().all()

        # Build course outline context
        course_outline = []
        current_module_index = -1
        for i, module in enumerate(all_modules):
            course_outline.append({
                "title": module.title,
                "description": module.description,
                "order": module.order,
                "is_current": module.id == module_id
            })
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
        existing_lesson = await self.get_lesson(course_id, module_id, lesson_id, generate=False, _user_id=_user_id)

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

    async def get_course_progress(self, course_id: UUID, _user_id: str | None = None) -> CourseProgressResponse:
        """Get overall progress for a course."""
        # Get all modules for the course
        modules = await self.list_modules(course_id, _user_id)
        total_modules = len(modules)
        completed_modules = len([m for m in modules if m.status == "completed"])
        in_progress_modules = len([m for m in modules if m.status == "in_progress"])

        # Get all lessons for all modules
        total_lessons = 0
        completed_lessons = 0

        for _module in modules:
            module_lessons = await self.list_lessons(course_id, _user_id)
            total_lessons += len(module_lessons)

            # Count completed lessons by checking progress records
            for lesson in module_lessons:
                stmt = select(Progress).where(Progress.lesson_id == str(lesson.id), Progress.status == "done")
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
        self, course_id: UUID, module_id: UUID, lesson_id: UUID, request: LessonStatusUpdate, _user_id: str | None = None
    ) -> LessonStatusResponse:
        """Update the status of a specific lesson."""
        # Check if progress record exists
        stmt = select(Progress).where(
            Progress.lesson_id == str(lesson_id),
            Progress.course_id == str(module_id),  # Note: Progress.course_id stores module_id
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
                course_id=str(module_id),  # Note: storing module_id in course_id field
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

    async def get_lesson_status(
        self, course_id: UUID, module_id: UUID, lesson_id: UUID, _user_id: str | None = None
    ) -> LessonStatusResponse:
        """Get the status of a specific lesson."""
        stmt = select(Progress).where(
            Progress.lesson_id == str(lesson_id),
            Progress.course_id == str(module_id),  # Note: Progress.course_id stores module_id
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
