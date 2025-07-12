"""Course content processor for tag generation."""

import json
import logging

from sqlalchemy import select

from src.courses.models import Course, CourseModule
from src.database.session import AsyncSession


logger = logging.getLogger(__name__)


class CourseProcessor:
    """Processor for extracting course content for tagging."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize course processor.

        Args:
            session: Database session
        """
        self.session = session

    async def extract_content_for_tagging(
        self,
        course: Course,
    ) -> dict[str, str]:
        """Extract course content for tag generation.

        Args:
            course: Course model instance

        Returns
        -------
            Dictionary with title and content_preview
        """
        try:
            # Get course modules for more detailed content
            result = await self.session.execute(
                select(CourseModule).where(CourseModule.roadmap_id == course.id).order_by(CourseModule.order)
            )
            modules = result.scalars().all()

            # Build comprehensive content preview
            content_preview = self._build_content_preview(
                course=course,
                modules=modules,
            )

            return {
                "title": course.title,
                "content_preview": content_preview,
            }

        except Exception as e:
            logger.exception(f"Error extracting course content for tagging: {e}")
            return {
                "title": course.title,
                "content_preview": course.description or "",
            }

    def _build_content_preview(
        self,
        course: Course,
        modules: list[CourseModule],
        max_length: int = 3000,
    ) -> str:
        """Build comprehensive content preview for tagging.

        Args:
            course: Course model instance
            modules: List of course modules
            max_length: Maximum preview length

        Returns
        -------
            Combined content preview
        """
        parts = []

        # Add course metadata
        parts.append(f"Title: {course.title}")

        if course.description:
            parts.append(f"Description: {course.description}")

        if course.skill_level:
            parts.append(f"Skill Level: {course.skill_level}")

        if course.tags_json:
            # Include existing tags if any
            try:
                existing_tags = json.loads(course.tags_json)
                if existing_tags:
                    parts.append(f"Existing tags: {', '.join(existing_tags)}")
            except Exception as e:
                logger.debug(f"Failed to parse existing tags: {e}")

        # Add module information for better context
        if modules:
            parts.append("\nCourse Structure:")
            for i, module in enumerate(modules[:10], 1):  # Limit to first 10 modules
                module_info = f"{i}. {module.title}"
                if module.description:
                    module_info += f": {module.description[:100]}"
                parts.append(module_info)

                # Include some module content if available
                if module.content and i <= 3:  # Only first 3 modules' content
                    content_preview = module.content[:200]
                    if len(module.content) > 200:
                        content_preview += "..."
                    parts.append(f"   Content: {content_preview}")

        # Combine and truncate
        preview = "\n\n".join(parts)

        if len(preview) > max_length:
            preview = preview[:max_length] + "..."

        return preview


async def process_course_for_tagging(
    course_id: str,
    session: AsyncSession,
) -> dict[str, str] | None:
    """Process a course to extract content for tagging.

    Args:
        course_id: ID of the course to process
        session: Database session

    Returns
    -------
        Dictionary with title and content_preview, or None if not found
    """
    # Get course from database
    result = await session.execute(
        select(Course).where(Course.id == course_id),
    )
    course = result.scalar_one_or_none()

    if not course:
        logger.error(f"Course not found: {course_id}")
        return None

    # Process course
    processor = CourseProcessor(session)
    return await processor.extract_content_for_tagging(course)
