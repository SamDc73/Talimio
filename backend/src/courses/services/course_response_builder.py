"""Course response builder service for constructing course responses."""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.courses.models import Node, Roadmap
from src.courses.schemas import CourseResponse, LessonResponse, ModuleResponse


class CourseResponseBuilder:
    """Service for building course response objects."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the response builder.

        Args:
            session: Database session
        """
        self.session = session

    async def build_module_response(self, module: Node, course_id: UUID) -> ModuleResponse:
        """Build a module response with lessons.

        Args:
            module: Module node
            course_id: Course ID

        Returns
        -------
            Module response with lessons
        """
        # Get lessons for this module
        lessons_query = select(Node).where(Node.parent_id == module.id).order_by(Node.order)

        lessons_result = await self.session.execute(lessons_query)
        lessons = [
            LessonResponse(
                id=lesson.id,
                course_id=lesson.roadmap_id,
                module_id=lesson.parent_id,
                title=lesson.title,
                description=lesson.description,
                content=lesson.content,  # None for placeholder lessons, content when generated
                created_at=lesson.created_at,
                updated_at=lesson.updated_at,
            )
            for lesson in lessons_result.scalars().all()
            if lesson.parent_id is not None  # Ensure we're only processing actual lessons
        ]

        return ModuleResponse(
            id=module.id,
            course_id=course_id,
            title=module.title,
            description=module.description,
            content=module.content,
            order=module.order,
            status=module.status,
            completion_percentage=module.completion_percentage,
            parent_id=module.parent_id,
            created_at=module.created_at,
            updated_at=module.updated_at,
            lessons=lessons,
        )

    def build_course_response_from_roadmap(
        self, roadmap: Roadmap, modules_data: list[ModuleResponse]
    ) -> CourseResponse:
        """Build a course response from a roadmap and modules.

        Args:
            roadmap: Roadmap model instance
            modules_data: List of module responses

        Returns
        -------
            Course response
        """
        return CourseResponse(
            id=roadmap.id,
            title=roadmap.title,
            description=roadmap.description,
            tags=roadmap.tags or "[]",
            archived=roadmap.archived,
            rag_enabled=roadmap.rag_enabled,
            modules=modules_data,
            created_at=roadmap.created_at,
            updated_at=roadmap.updated_at,
        )

    @staticmethod
    def build_course_list(courses: Any) -> list[CourseResponse]:
        """Build a list of course responses from course models.

        Args:
            courses: List of Course/Roadmap model instances

        Returns
        -------
            List of course responses
        """
        course_responses = []
        for course in courses:
            course_response = CourseResponse(
                id=course.id,
                title=course.title,
                description=course.description,
                tags=course.tags or "[]",
                archived=course.archived,
                rag_enabled=course.rag_enabled,
                modules=[],  # Empty modules for list view
                created_at=course.created_at,
                updated_at=course.updated_at,
            )
            course_responses.append(course_response)
        return course_responses
