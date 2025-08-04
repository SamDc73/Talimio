"""Course content service extending BaseContentService."""

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.base_service import BaseContentService
from src.courses.models import Course
from src.database.session import async_session_maker


logger = logging.getLogger(__name__)


class CourseContentService(BaseContentService):
    """Course service with shared content behavior."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        super().__init__()
        self.session = session

    def _get_content_type(self) -> str:
        """Return the content type for this service."""
        return "course"

    async def _do_create(self, data: dict, user_id: UUID) -> Course:
        """Create a new course."""
        async with async_session_maker() as session:
            # Convert tags to JSON if present
            if "tags" in data and data["tags"] is not None:
                data["tags"] = json.dumps(data["tags"])

            # Create course instance
            course = Course(**data, user_id=user_id, created_at=datetime.now(UTC), updated_at=datetime.now(UTC))

            session.add(course)
            await session.commit()
            await session.refresh(course)

            logger.info(f"Created course {course.id} for user {user_id}")
            return course

    async def _do_update(self, content_id: UUID, data: dict, user_id: UUID) -> Course:
        """Update an existing course."""
        async with async_session_maker() as session:
            # Get the course
            query = select(Course).where(Course.id == content_id, Course.user_id == user_id)
            result = await session.execute(query)
            course = result.scalar_one_or_none()

            if not course:
                msg = f"Course {content_id} not found"
                raise ValueError(msg)

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

    async def _do_delete(self, content_id: UUID, user_id: UUID) -> bool:
        """Delete a course."""
        async with async_session_maker() as session:
            # Get the course
            query = select(Course).where(Course.id == content_id, Course.user_id == user_id)
            result = await session.execute(query)
            course = result.scalar_one_or_none()

            if not course:
                return False

            # Delete the course (cascade will handle related records)
            await session.delete(course)
            await session.commit()

            logger.info(f"Deleted course {content_id}")
            return True

    def _needs_ai_processing(self, content: Course) -> bool:
        """Check if course needs AI processing after creation."""
        # Courses might need AI processing for content generation
        return content.generation_status == "pending"

    def _needs_ai_reprocessing(self, content: Course, updated_data: dict) -> bool:
        """Check if course needs AI reprocessing after update."""
        # Reprocess if key fields change
        _ = content  # Currently unused but kept for future use
        significant_fields = {"title", "description", "level", "duration"}
        return any(field in updated_data for field in significant_fields)

    async def _update_progress(self, content_id: UUID, user_id: UUID, status: str) -> None:
        """Update progress tracking for course."""
        try:
            # For courses, we track lesson progress separately
            # This is just for creation status
            _ = user_id  # Currently unused but kept for future use
            logger.info(f"Course {content_id} status: {status}")
        except Exception as e:
            logger.exception(f"Failed to update course progress: {e}")
