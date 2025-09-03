"""Course content service for course-specific operations."""

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.ai_service import AIService
from src.courses.models import Course
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
            # Process AI prompt if present
            if "prompt" in data:
                prompt = data.pop("prompt")  # Remove prompt from data
                # Generate course data from prompt using AI
                course_data = await self._generate_course_from_prompt(prompt, user_id)
                # Merge AI-generated data with any provided data
                data.update(course_data)

            # Convert tags to JSON if present
            if "tags" in data and data["tags"] is not None:
                data["tags"] = json.dumps(data["tags"])

            # Create course instance
            course = Course(**data, user_id=user_id, created_at=datetime.now(UTC), updated_at=datetime.now(UTC))

            session.add(course)
            await session.commit()
            await session.refresh(course)

            logger.info(f"Created course {course.id} for user {user_id}")

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

            # Update fields
            for field, value in data.items():
                if field == "tags" and value is not None:
                    setattr(course, field, json.dumps(value))
                else:
                    setattr(course, field, value)

            course.updated_at = datetime.now(UTC)

            await session.commit()
            await session.refresh(course)

            logger.info(f"Updated course {course.id}")
            return course

    async def delete_course(self, course_id: UUID, user_id: UUID) -> bool:
        """Delete a course."""
        async with async_session_maker() as session:
            # Get the course
            query = select(Course).where(Course.id == course_id, Course.user_id == user_id)
            result = await session.execute(query)
            course = result.scalar_one_or_none()

            if not course:
                return False

            # Delete the course (cascade will handle related records)
            await session.delete(course)
            await session.commit()

            logger.info(f"Deleted course {course_id}")
            return True

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
        """Generate course data from AI prompt."""
        try:
            # Use AI service to generate course structure from prompt
            ai_result = await self.ai_service.process_content(
                content_type="course",
                content_id="",  # New course, no ID yet
                user_id=user_id,
                data={
                    "prompt": prompt,
                    "operation": "generate_course"
                }
            )

            if not ai_result.get("success"):
                logger.error(f"AI course generation failed: {ai_result.get('error', 'Unknown error')}")
                # Fall back to basic course structure
                return self._create_fallback_course_data(prompt)

            # Extract course data from AI response
            course_data = ai_result.get("result", {})

            # Ensure required fields are present with defaults
            return {
                "title": course_data.get("title", f"Course: {prompt[:50]}..."),
                "description": course_data.get("description", f"A course about {prompt}"),
                "tags": course_data.get("tags", []),
                "rag_enabled": False,  # Default to false for new courses
                "archived": False,
            }

        except Exception as e:
            logger.exception(f"Error generating course from prompt '{prompt}': {e}")
            return self._create_fallback_course_data(prompt)

    def _create_fallback_course_data(self, prompt: str) -> dict:
        """Create fallback course data when AI generation fails."""
        return {
            "title": f"Course: {prompt[:50]}..." if len(prompt) > 50 else f"Course: {prompt}",
            "description": f"A course about {prompt}",
            "tags": [],
            "rag_enabled": False,
            "archived": False,
        }
