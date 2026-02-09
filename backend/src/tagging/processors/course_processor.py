"""Course content processor for tag generation."""

import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.courses.models import Course, Lesson


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
            lessons_result = await self.session.execute(
                select(Lesson)
                .where(Lesson.course_id == course.id)
                .order_by(Lesson.module_order.is_(None), Lesson.module_order, Lesson.order)
            )
            lessons: list[Lesson] = list(lessons_result.scalars().all())

            content_preview = self._build_content_preview(
                course=course,
                lessons=lessons,
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
        lessons: list[Lesson],
        max_length: int = 3000,
    ) -> str:
        """Build comprehensive content preview for tagging."""
        parts: list[str] = []

        # Add course metadata
        self._add_course_metadata(course, parts)

        module_groups = self._group_lessons_by_module(lessons)
        if module_groups:
            self._add_module_outline(module_groups, parts)
            self._add_module_content_preview(module_groups, parts)

        preview = "\n\n".join(parts)
        return self._truncate_preview(preview, max_length)

    def _group_lessons_by_module(self, lessons: list[Lesson]) -> list[dict[str, Any]]:
        """Group lessons by module name while preserving ordering."""
        groups: dict[str, dict[str, Any]] = {}
        for index, lesson in enumerate(lessons):
            module_name = lesson.module_name or "Lessons"
            entry = groups.setdefault(
                module_name,
                {
                    "order": lesson.module_order,
                    "lessons": [],
                    "first_index": index,
                },
            )

            if lesson.module_order is not None:
                current_order = entry.get("order")
                if current_order is None or lesson.module_order < current_order:
                    entry["order"] = lesson.module_order

            entry["lessons"].append(lesson)
            entry["first_index"] = min(entry["first_index"], index)

        return sorted(
            (
                {
                    "name": name,
                    "order": data.get("order"),
                    "lessons": data["lessons"],
                    "first_index": data["first_index"],
                }
                for name, data in groups.items()
            ),
            key=lambda item: (
                item["order"] is None,
                item["order"] if item["order"] is not None else item["first_index"],
                item["first_index"],
            ),
        )


    def _add_course_metadata(self, course: Course, parts: list[str]) -> None:
        """Add course metadata to preview parts."""
        if course.description:
            parts.append(f"Description: {course.description}")

        self._add_existing_tags(course, parts)

    def _add_existing_tags(self, course: Course, parts: list[str]) -> None:
        """Add existing tags to preview parts."""
        if course.tags:
            try:
                existing_tags = json.loads(course.tags)
                if existing_tags:
                    parts.append(f"Existing tags: {', '.join(existing_tags)}")
            except Exception as e:
                logger.debug(f"Failed to parse existing tags: {e}")

    def _add_module_outline(self, modules: list[dict[str, Any]], parts: list[str]) -> None:
        """Add module outline to preview parts."""
        if not modules:
            return

        parts.append("Course Outline:")
        outline_entries: list[str] = []
        for i, module in enumerate(modules[:20], 1):  # First 20 modules like ToC
            outline_entries.append(
                f"{i}. {module['name']} ({len(module['lessons'])} lessons)"
            )

        if outline_entries:
            parts.append("\n".join(outline_entries))

    def _add_module_content_preview(self, modules: list[dict[str, Any]], parts: list[str]) -> None:
        """Add detailed module content preview."""
        if not modules:
            return

        parts.append("\nModule Highlights:")
        for i, module in enumerate(modules[:5], 1):  # Provide detail for first 5 modules
            module_name = module["name"]
            parts.append(f"\nModule {i}: {module_name}")

            lessons = module["lessons"]
            for lesson in lessons[:3]:  # Summarize first 3 lessons per module
                summary = self._summarize_lesson(lesson)
                parts.append(f"- {lesson.title}: {summary}")

    def _summarize_lesson(self, lesson: Lesson) -> str:
        """Summarize a lesson's description/content for tagging."""
        source = lesson.description or lesson.content or ""
        if not source:
            return "No additional details provided."
        return self._truncate_text(source.strip(), 280)

    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text to max length with ellipsis."""
        if len(text) > max_length:
            return text[:max_length] + "..."
        return text

    def _truncate_preview(self, preview: str, max_length: int) -> str:
        """Truncate preview to max length."""
        if len(preview) > max_length:
            return preview[:max_length] + "..."
        return preview


async def process_course_for_tagging(
    course_id: UUID,
    user_id: UUID,
    session: AsyncSession,
) -> dict[str, str] | None:
    """Process a course to extract content for tagging.

    Args:
        course_id: ID of the course to process
        user_id: Owner user ID
        session: Database session

    Returns
    -------
        Dictionary with title and content_preview, or None if not found
    """
    result = await session.execute(
        select(Course).where(Course.id == course_id, Course.user_id == user_id),
    )
    course = result.scalar_one_or_none()

    if not course:
        logger.error(f"Course not found: {course_id}")
        return None

    processor = CourseProcessor(session)
    return await processor.extract_content_for_tagging(course)
