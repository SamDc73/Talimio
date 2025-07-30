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
        self._add_course_metadata(course, parts)

        # Add module information
        if modules:
            self._add_module_outline(modules, parts)
            self._add_module_content_preview(modules, parts)

        # Combine and truncate
        preview = "\n\n".join(parts)
        return self._truncate_preview(preview, max_length)

    def _add_course_metadata(self, course: Course, parts: list[str]) -> None:
        """Add course metadata to preview parts.

        Args:
            course: Course model instance
            parts: List to append metadata to
        """
        if course.description:
            parts.append(f"Description: {course.description}")

        if course.skill_level:
            parts.append(f"Skill Level: {course.skill_level}")

        self._add_existing_tags(course, parts)

    def _add_existing_tags(self, course: Course, parts: list[str]) -> None:
        """Add existing tags to preview parts.

        Args:
            course: Course model instance
            parts: List to append tags to
        """
        if course.tags:
            try:
                existing_tags = json.loads(course.tags)
                if existing_tags:
                    parts.append(f"Existing tags: {', '.join(existing_tags)}")
            except Exception as e:
                logger.debug(f"Failed to parse existing tags: {e}")

    def _add_module_outline(self, modules: list[CourseModule], parts: list[str]) -> None:
        """Add module outline to preview parts.

        Args:
            modules: List of course modules
            parts: List to append outline to
        """
        parts.append("Course Outline:")
        module_titles = []
        for i, module in enumerate(modules[:20], 1):  # First 20 modules like ToC
            module_titles.append(f"{i}. {module.title}")

        if module_titles:
            parts.append("\n".join(module_titles))

    def _add_module_content_preview(self, modules: list[CourseModule], parts: list[str]) -> None:
        """Add detailed module content preview.

        Args:
            modules: List of course modules
            parts: List to append content to
        """
        parts.append("\nContent Preview:")
        for i, module in enumerate(modules[:5], 1):  # First 5 modules detailed content
            if module.description or module.content:
                parts.append(f"\nModule {i}: {module.title}")
                self._add_module_details(module, parts)

    def _add_module_details(self, module: CourseModule, parts: list[str]) -> None:
        """Add module description and content details.

        Args:
            module: Course module instance
            parts: List to append details to
        """
        if module.description:
            desc_preview = self._truncate_text(module.description, 300)
            parts.append(f"Description: {desc_preview}")

        if module.content:
            content_preview = self._truncate_text(module.content, 500)
            parts.append(f"Content: {content_preview}")

    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text to max length with ellipsis.

        Args:
            text: Text to truncate
            max_length: Maximum length

        Returns
        -------
            Truncated text
        """
        if len(text) > max_length:
            return text[:max_length] + "..."
        return text

    def _truncate_preview(self, preview: str, max_length: int) -> str:
        """Truncate preview to max length.

        Args:
            preview: Preview text
            max_length: Maximum length

        Returns
        -------
            Truncated preview
        """
        if len(preview) > max_length:
            return preview[:max_length] + "..."
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
