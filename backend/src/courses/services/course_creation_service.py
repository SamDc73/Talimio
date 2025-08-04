"""Course creation service for creating new courses."""

import logging
import os
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.ai_service import AIServiceError, get_ai_service
from src.ai.memory import Mem0Wrapper
from src.courses.models import Node, Roadmap
from src.courses.schemas import CourseCreate, CourseResponse, ModuleResponse
from src.courses.services.course_response_builder import CourseResponseBuilder


class CourseCreationService:
    """Service for creating new courses."""

    def __init__(self, session: AsyncSession, user_id: UUID | None = None) -> None:
        """Initialize the course creation service.

        Args:
            session: Database session
            user_id: User ID for user-specific operations
        """
        self.session = session
        self.user_id = user_id
        self._logger = logging.getLogger(__name__)
        self.response_builder = CourseResponseBuilder(session)

        # Initialize AI service
        self._ai_service = get_ai_service()

        # Initialize memory service
        try:
            # Skip memory service in mock mode
            if os.getenv("MOCK_AI_SERVICES") == "true":
                self.memory_service = None
            else:
                self.memory_service = Mem0Wrapper() if user_id else None
            self._logger.info(f"Memory service initialized: {self.memory_service is not None}, user_id: {user_id}")
        except Exception as e:
            self._logger.exception(f"Failed to initialize memory service: {e}")
            self.memory_service = None

    async def create_course(self, request: CourseCreate, user_id: UUID) -> CourseResponse:
        """Create a new course using AI generation.

        Args:
            request: Course creation request
            user_id: User ID

        Returns
        -------
            Created course response

        Raises
        ------
            HTTPException: If course creation fails
        """
        self._logger.info("Creating course for user %s with prompt: %s...", user_id, request.prompt[:100])

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

        try:
            # Generate course structure using AI service
            roadmap_response = await self._ai_service.process_content(
                content_type="course",
                action="generate",
                user_id=user_id,
                topic=request.prompt,
                skill_level="beginner",
                description=enhanced_prompt,
                use_tools=True,  # Enable content discovery
            )

            course_title = roadmap_response["title"]
            course_description = roadmap_response["description"]
            nodes_data = roadmap_response["coreTopics"]

            # Check for duplicate title (basic validation)
            title = course_title
            existing_query = select(Roadmap).where(Roadmap.title == title, Roadmap.user_id == user_id)
            existing_course = await self.session.execute(existing_query)
            if existing_course.scalar_one_or_none():
                # Add timestamp to make it unique
                title = f"{title} ({datetime.now(UTC).strftime('%Y-%m-%d %H:%M')})"

            # Create the main roadmap/course
            roadmap = Roadmap(
                title=title,
                description=course_description,
                skill_level=roadmap_response.get("difficulty", "beginner"),
                user_id=user_id,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

            self.session.add(roadmap)
            await self.session.flush()  # Get the ID without committing

            # Create modules and lessons from the AI-generated structure
            modules_data = await self._create_modules_and_lessons(roadmap.id, nodes_data)

            await self.session.commit()
            await self.session.refresh(roadmap)

            # Apply automatic tagging (non-blocking - don't fail course creation if tagging fails)
            try:
                from src.tagging.service import apply_automatic_tagging_to_course

                await apply_automatic_tagging_to_course(self.session, roadmap, modules_data)
                await self.session.commit()
                await self.session.refresh(roadmap)
            except Exception as tagging_error:
                self._logger.warning("Failed to apply automatic tagging to course %s: %s", roadmap.id, tagging_error)
                # Continue with course creation even if tagging fails

            # Store in memory service if available
            if self.memory_service:
                try:
                    await self.memory_service.store_course_context(
                        user_id,
                        {
                            "course_id": str(roadmap.id),
                            "title": roadmap.title,
                            "description": roadmap.description,
                            "modules": modules_data,
                        },
                    )
                except Exception as e:
                    self._logger.warning("Failed to store course in memory service: %s", e)

            self._logger.info("Successfully created course %s for user %s", roadmap.id, user_id)

            return self.response_builder.build_course_response_from_roadmap(roadmap, modules_data)

        except AIServiceError as e:
            self._logger.exception("AI service error during course creation")
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI service error: {e!s}") from e
        except Exception as e:
            self._logger.exception("Unexpected error during course creation")
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create course"
            ) from e

    async def _create_modules_and_lessons(self, roadmap_id: UUID, nodes_data: list) -> list[ModuleResponse]:
        """Create modules and lessons from AI-generated data.

        Args:
            roadmap_id: The roadmap ID
            nodes_data: List of module data from AI

        Returns
        -------
            List of module responses with lessons
        """
        modules_data = []

        for i, module_data in enumerate(nodes_data):
            module_node = Node(
                title=module_data.get("title", f"Module {i + 1}"),
                description=module_data.get("description", ""),
                roadmap_id=roadmap_id,
                parent_id=None,
                order=i,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            self.session.add(module_node)
            await self.session.flush()

            # Collect lessons for this module
            lessons_data = []
            # Check for both "subtopics" and "children" fields as the AI client uses "children"
            subtopics = module_data.get("subtopics", module_data.get("children", []))
            for j, lesson_data in enumerate(subtopics):
                lesson_node = Node(
                    title=lesson_data.get("title", f"Lesson {j + 1}"),
                    description=lesson_data.get("description", ""),
                    roadmap_id=roadmap_id,
                    parent_id=module_node.id,
                    order=j,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
                self.session.add(lesson_node)
                await self.session.flush()

                # Add lesson to lessons_data list
                lessons_data.append(self.response_builder.build_lesson_response(lesson_node))

            modules_data.append(
                ModuleResponse(
                    id=module_node.id,
                    course_id=roadmap_id,
                    title=module_node.title,
                    description=module_node.description,
                    content=module_node.content,
                    order=module_node.order,
                    status=module_node.status,
                    completion_percentage=module_node.completion_percentage,
                    parent_id=module_node.parent_id,
                    created_at=module_node.created_at,
                    updated_at=module_node.updated_at,
                    lessons=lessons_data,
                )
            )

        return modules_data
