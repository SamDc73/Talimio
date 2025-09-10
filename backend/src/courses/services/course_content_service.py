"""Course content service for course-specific operations."""

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.ai_service import AIService
from src.courses.models import Course, CourseModule
from src.database.session import async_session_maker


logger = logging.getLogger(__name__)


class CourseContentService:
    """Course service handling course-specific content operations."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session
        self.ai_service = AIService()

    async def create_course(self, data: dict, user_id: UUID) -> Course:
        """Create a new course."""
        async with async_session_maker() as session:
            session.expire_on_commit = False  # Keep objects accessible after commit

            # Process AI prompt if present
            if "prompt" in data:
                prompt = data.pop("prompt")  # Remove prompt from data
                # Generate course data from prompt using AI
                course_data = await self._generate_course_from_prompt(prompt, user_id)
                # Merge AI-generated data with any provided data
                data.update(course_data)

            # Extract modules before creating the course
            modules = data.pop("modules", [])

            # Convert tags to JSON string if present and provided as list
            if "tags" in data and data["tags"] is not None:
                if isinstance(data["tags"], (list, tuple)):
                    data["tags"] = json.dumps(list(data["tags"]))
                elif isinstance(data["tags"], str):
                    # Assume already JSON-encoded
                    pass
                else:
                    # Best-effort serialization
                    data["tags"] = json.dumps(data["tags"])  # type: ignore[arg-type]

            # Create course instance
            course = Course(**data, user_id=user_id, created_at=datetime.now(UTC), updated_at=datetime.now(UTC))

            session.add(course)
            await session.commit()
            await session.refresh(course)

            logger.info(f"Created course {course.id} for user {user_id}")

            # Create nodes from modules
            if modules:
                await self._create_course_nodes(session, course.id, modules)

            # Auto-generate tags from course content
            try:
                await self._auto_tag_course(session, course, user_id)
            except Exception as e:
                logger.warning(f"Automatic tagging failed for course {course.id}: {e}")

            return course

    async def update_course(self, course_id: UUID, data: dict, user_id: UUID) -> Course:
        """Update an existing course."""
        async with async_session_maker() as session:
            # Get the course
            query = select(Course).where(Course.id == course_id, Course.user_id == user_id)
            result = await session.execute(query)
            course = result.scalar_one_or_none()

            if not course:
                error_msg = f"Course {course_id} not found"
                raise ValueError(error_msg)

            # Update fields - skip None values to avoid writing NULLs to NOT NULL columns
            for field, value in data.items():
                if value is None:
                    continue
                if field == "tags":
                    # Accept list/tuple or JSON string
                    if isinstance(value, (list, tuple)):
                        setattr(course, field, json.dumps(list(value)))
                    elif isinstance(value, str):
                        setattr(course, field, value)
                    else:
                        try:
                            setattr(course, field, json.dumps(value))
                        except Exception:
                            logger.warning(
                                "Ignoring unsupported tags value type for course %s: %r", course_id, type(value)
                            )
                    continue
                # All other fields: apply directly
                setattr(course, field, value)

            course.updated_at = datetime.now(UTC)

            await session.commit()
            await session.refresh(course)

            logger.info(f"Updated course {course.id}")
            return course

    async def _auto_tag_course(self, session: AsyncSession, course: Course, user_id: UUID) -> list[str]:
        """Generate tags for a course using its content preview and store them."""
        try:
            from src.tagging.processors.course_processor import process_course_for_tagging
            from src.tagging.service import TaggingService

            # Extract content preview for tagging
            content_data = await process_course_for_tagging(str(course.id), session)
            if not content_data:
                logger.warning(f"Course {course.id} not found or no content data for tagging")
                return []

            # Generate tags via TaggingService
            tagging_service = TaggingService(session)
            tags = await tagging_service.tag_content(
                content_id=course.id,
                content_type="course",
                user_id=user_id,
                title=content_data.get("title", ""),
                content_preview=content_data.get("content_preview", ""),
            )

            # Persist tags onto the Course model for backward compatibility
            if tags:
                course.tags = json.dumps(tags)
                await session.commit()
                logger.info(f"Successfully tagged course {course.id} with {len(tags)} tags")

            return tags or []

        except Exception as e:
            logger.exception(f"Auto-tagging error for course {course.id}: {e}")
            return []

    async def _generate_course_from_prompt(self, prompt: str, user_id: UUID) -> dict:
        """Generate course data from AI prompt. Fails fast on error/timeout."""
        # Use centralized AI service (timeouts/retries handled there)
        ai_result = await self.ai_service.process_content(
            content_type="course",
            action="generate",
            user_id=user_id,
            topic=prompt,
        )

        # AI service returns a roadmap dict, not a wrapped {success, result}
        if not isinstance(ai_result, dict):
            error_msg = "Invalid AI response format for course generation"
            raise TypeError(error_msg)

        course_data = ai_result

        # Ensure required fields are present with defaults
        title = course_data.get("title")
        description = course_data.get("description")
        if not title:
            error_msg = "AI generation returned no title"
            raise RuntimeError(error_msg)

        return {
            "title": title,
            "description": description or f"A course about {prompt}",
            "tags": course_data.get("tags", []),
            # Include the generated course structure with new naming
            "modules": course_data.get("modules", []),
            # Rely on DB defaults for archived/rag_enabled; include if provided
            **({"rag_enabled": course_data["rag_enabled"]} if "rag_enabled" in course_data else {}),
            **({"archived": course_data["archived"]} if "archived" in course_data else {}),
        }

    async def _create_course_nodes(
        self, session: AsyncSession, course_id: UUID, modules: list[dict], parent_id: UUID | None = None
    ) -> None:
        """Recursively create course nodes (modules and lessons) from the AI-generated structure.

        Args:
            session: Database session
            course_id: Course ID
            modules: List of module dictionaries with title, description, and lessons
            parent_id: Parent node ID for nested structure
        """
        for order, module in enumerate(modules):
            # Create module node
            node = CourseModule(
                roadmap_id=course_id,
                title=module.get("title", "Untitled"),
                description=module.get("description", ""),
                order=order,
                parent_id=parent_id,
                status="not_started",
                completion_percentage=0.0,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            session.add(node)
            await session.flush()  # Get the node ID for nested lessons

            # Create lessons for this module
            lessons = module.get("lessons", [])
            if lessons:
                await self._create_course_nodes(session, course_id, lessons, parent_id=node.id)

        # Commit all nodes together
        if parent_id is None:  # Only commit at the top level
            await session.commit()
            logger.info(f"Created {len(modules)} modules for course {course_id}")
