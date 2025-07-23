"""Course creation service for creating new courses."""

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.client import AIError, ModelManager
from src.ai.memory import Mem0Wrapper
from src.courses.models import Node, Roadmap
from src.courses.schemas import CourseCreate, CourseResponse, ModuleResponse
from src.courses.services.course_response_builder import CourseResponseBuilder
from src.tagging.service import TaggingService


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
        self.ai_client = ModelManager()
        self.memory_service = Mem0Wrapper() if user_id else None
        self.response_builder = CourseResponseBuilder(session)
        self._logger = logging.getLogger(__name__)

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
        effective_user_id = user_id or self.user_id

        self._logger.info("Creating course for user %s with prompt: %s...", effective_user_id, request.prompt[:100])
        self._logger.info("Current AI model: %s", self.ai_client.model)

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
            # Generate course structure using AI with function calling enabled
            roadmap_response = await self.ai_client.generate_roadmap_content(
                user_prompt=request.prompt,
                skill_level="beginner",
                description=enhanced_prompt,
                use_tools=True,  # Enable content discovery
            )

            course_title = roadmap_response["title"]
            course_description = roadmap_response["description"]
            nodes_data = roadmap_response["coreTopics"]

            # Check for duplicate title (basic validation)
            title = course_title
            existing_query = select(Roadmap).where(
                Roadmap.title == title
            )
            existing_course = await self.session.execute(existing_query)
            if existing_course.scalar_one_or_none():
                # Add timestamp to make it unique
                title = f"{title} ({datetime.now(UTC).strftime('%Y-%m-%d %H:%M')})"

            # Create the main roadmap/course
            roadmap = Roadmap(
                title=title,
                description=course_description,
                skill_level=roadmap_response.get("difficulty", "beginner"),
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

            self.session.add(roadmap)
            await self.session.flush()  # Get the ID without committing

            # Create modules and lessons from the AI-generated structure
            modules_data = await self._create_modules_and_lessons(roadmap.id, nodes_data)

            await self.session.commit()

            # Apply automatic tagging
            await self._apply_automatic_tagging(roadmap, modules_data)

            # Store in memory service if available
            if self.memory_service:
                try:
                    await self.memory_service.store_course_context(
                        effective_user_id,
                        {
                            "course_id": str(roadmap.id),
                            "title": roadmap.title,
                            "description": roadmap.description,
                            "modules": modules_data,
                        }
                    )
                except Exception as e:
                    self._logger.warning("Failed to store course in memory service: %s", e)

            self._logger.info("Successfully created course %s for user %s", roadmap.id, effective_user_id)

            return self.response_builder.build_course_response_from_roadmap(
                roadmap, modules_data
            )

        except AIError as e:
            self._logger.exception("AI service error during course creation")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI service error: {e!s}"
            ) from e
        except Exception as e:
            self._logger.exception("Unexpected error during course creation")
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create course"
            ) from e

    async def _create_modules_and_lessons(
        self, roadmap_id: UUID, nodes_data: list
    ) -> list[ModuleResponse]:
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
                lessons_data.append(
                    self.response_builder.build_lesson_response(lesson_node)
                )

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

    async def _apply_automatic_tagging(self, roadmap: Roadmap, modules_data: list[ModuleResponse]) -> None:
        """Apply automatic tagging to the course/roadmap.

        Args:
            roadmap: The created roadmap
            modules_data: List of module data for context
        """
        try:
            # Initialize tagging service
            tagging_service = TaggingService(self.session, self.ai_client)

            # Build content preview from roadmap and modules
            content_preview = self._build_content_preview(roadmap, modules_data)

            # Generate and store tags
            tags = await tagging_service.tag_content(
                content_id=roadmap.id,
                content_type="roadmap",
                title=roadmap.title,
                content_preview=content_preview,
            )

            if tags:
                # Update the roadmap's tags_json field
                roadmap.tags_json = json.dumps(tags)
                await self.session.commit()
                self._logger.info("Successfully tagged course %s with tags: %s", roadmap.id, tags)

        except Exception as e:
            self._logger.exception("Failed to tag course %s: %s", roadmap.id, e)
            # Don't fail the entire course creation if tagging fails

    def _build_content_preview(self, roadmap: Roadmap, modules_data: list[ModuleResponse]) -> str:
        """Build content preview for tagging.

        Args:
            roadmap: The created roadmap
            modules_data: List of module data

        Returns
        -------
            Content preview string
        """
        parts = []

        # Add roadmap description
        parts.append(f"Title: {roadmap.title}")
        if roadmap.description:
            parts.append(f"Description: {roadmap.description}")

        # Add skill level
        parts.append(f"Skill Level: {roadmap.skill_level}")

        # Add module information
        if modules_data:
            parts.append("\nCourse Structure:")
            for i, module in enumerate(modules_data[:10], 1):  # Limit to first 10 modules
                module_info = f"{i}. {module.title}"
                if module.description:
                    module_info += f": {module.description[:100]}"
                    if len(module.description) > 100:
                        module_info += "..."
                parts.append(module_info)

                # Include some lesson titles for better context
                if module.lessons and i <= 3:  # Only first 3 modules' lessons
                    for _j, lesson in enumerate(module.lessons[:3], 1):
                        parts.append(f"   - {lesson.title}")

        return "\n".join(parts)
