"""Course content service for course-specific operations."""

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.service import AIService
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

            # Convert setup_commands to JSON string if present
            if "setup_commands" in data and data["setup_commands"] is not None:
                if isinstance(data["setup_commands"], (list, tuple)):
                    data["setup_commands"] = json.dumps(list(data["setup_commands"]))
                elif isinstance(data["setup_commands"], str):
                    pass  # Already JSON-encoded
                else:
                    data["setup_commands"] = json.dumps(data["setup_commands"])  # type: ignore[arg-type]

            # Create course instance
            course = Course(**data, user_id=user_id, created_at=datetime.now(UTC), updated_at=datetime.now(UTC))

            session.add(course)
            await session.flush()  # Flush to get the ID without committing

            # Create nodes from modules in the same transaction
            if modules:
                await self._create_course_nodes(session, course.id, modules)
            else:
                logger.warning(f"No modules to create for course {course.id}")

            # Commit everything together
            await session.commit()
            await session.refresh(course)

            # Auto-generate tags from course content
            try:
                await self._auto_tag_course(session, course, user_id)
            except Exception as e:
                logger.warning(f"Automatic tagging failed for course {course.id}: {e}")

            # Single log for entire operation
            module_count = len(modules) if modules else 0
            logger.info(f"Created course {course.id} with {module_count} modules")

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

            return tags or []

        except Exception as e:
            logger.exception(f"Auto-tagging error for course {course.id}: {e}")
            return []

    async def _generate_course_from_prompt(self, prompt: str, user_id: UUID) -> dict:
        """Generate course data from AI prompt. Fails fast on error/timeout."""
        # Use the actual course_generate method that exists on AIService
        ai_result = await self.ai_service.course_generate(
            user_id=user_id,
            topic=prompt,
        )

        # AI service returns a CourseStructure object
        if not ai_result:
            error_msg = "Invalid AI response format for course generation"
            raise TypeError(error_msg)

        # Convert CourseStructure to dict
        course_data = ai_result.model_dump() if hasattr(ai_result, "model_dump") else ai_result

        # Ensure required fields are present with defaults
        title = course_data.get("title")
        description = course_data.get("description")
        if not title:
            error_msg = "AI generation returned no title"
            raise RuntimeError(error_msg)

        # Transform flat lessons into modules with lessons
        lessons = course_data.get("lessons", [])
        modules = []

        if lessons:
            # Group lessons by module field if present, otherwise create single module
            module_map = {}
            for lesson in lessons:
                raw_module_name = lesson.get("module")
                if isinstance(raw_module_name, str):
                    module_name = raw_module_name.strip() or "Core Concepts"
                else:
                    module_name = "Core Concepts"

                normalized_key = module_name
                if normalized_key not in module_map:
                    module_map[normalized_key] = {
                        "title": module_name,
                        "description": f"Learn about {module_name.lower()}",
                        "lessons": []
                    }
                module_map[normalized_key]["lessons"].append({
                    "title": lesson.get("title", ""),
                    "description": lesson.get("description", "")
                })

            modules = list(module_map.values())
        else:
            logger.warning("AI generated no lessons")

        result = {
            "title": title,
            "description": description or f"A course about {prompt}",
            "tags": course_data.get("tags", []),
            "setup_commands": course_data.get("setup_commands", []),
            "modules": modules,
        }

        # Add optional fields if present
        if "archived" in course_data:
            result["archived"] = course_data["archived"]

        return result

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

