"""Course content service for course-specific operations."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from sqlalchemy import select

from src.ai.service import AIService
from src.courses.models import Course, Lesson
from src.database.session import async_session_maker


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)


class CourseContentService:
    """Course service handling course-specific content operations."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session
        self.ai_service = AIService()

    async def create_course(
        self,
        data: dict[str, Any],
        user_id: UUID,
        session: AsyncSession | None = None,
    ) -> Course:
        """Create a new course and populate its lessons."""
        working_session = session or self.session

        if working_session is not None:
            return await self._create_course_with_session(working_session, data, user_id)

        async with async_session_maker() as managed_session:
            return await self._create_course_with_session(managed_session, data, user_id)

    async def _create_course_with_session(
        self,
        session: AsyncSession,
        data: dict[str, Any],
        user_id: UUID,
    ) -> Course:
        """Create a course using the provided session."""
        session_data = dict(data)

        if "prompt" in session_data:
            prompt = session_data.pop("prompt")
            generated = await self._generate_course_from_prompt(prompt, user_id)
            session_data.update(generated)

        modules_payload = session_data.pop("modules", [])
        lessons_payload = session_data.pop("lessons", [])
        normalized_modules = self._normalize_modules_payload(modules_payload, lessons_payload)

        if "tags" in session_data and session_data["tags"] is not None:
            session_data["tags"] = self._ensure_json_string(session_data["tags"])

        if "setup_commands" in session_data and session_data["setup_commands"] is not None:
            session_data["setup_commands"] = self._ensure_json_string(session_data["setup_commands"])

        course = Course(user_id=user_id, **session_data)
        session.add(course)

        try:
            await session.flush()
            inserted_lessons = await self._insert_lessons(session, course.id, normalized_modules)
            await session.commit()
        except Exception:
            await session.rollback()
            raise

        await session.refresh(course)

        try:
            await self._auto_tag_course(session, course, user_id)
        except Exception as exc:
            logger.warning("Automatic tagging failed for course %s: %s", course.id, exc)

        module_count = sum(1 for module in normalized_modules if module.get("title"))
        logger.info(
            "Created course %s with %d lessons across %d modules",
            course.id,
            inserted_lessons,
            module_count,
        )

        return course

    async def update_course(self, course_id: UUID, data: dict[str, Any], user_id: UUID) -> Course:
        """Update an existing course."""
        async with async_session_maker() as session:
            query = select(Course).where(Course.id == course_id, Course.user_id == user_id)
            result = await session.execute(query)
            course = result.scalar_one_or_none()
            if not course:
                error_msg = f"Course {course_id} not found"
                raise ValueError(error_msg)

            for field, value in data.items():
                if value is None:
                    continue
                if field in {"tags", "setup_commands"}:
                    setattr(course, field, self._ensure_json_string(value))
                    continue
                setattr(course, field, value)

            course.updated_at = datetime.now(UTC)

            await session.commit()
            await session.refresh(course)

            return course

    async def _auto_tag_course(self, session: AsyncSession, course: Course, user_id: UUID) -> list[str]:
        """Generate tags for a course using its content preview and persist them."""
        try:
            from src.tagging.processors.course_processor import process_course_for_tagging
            from src.tagging.service import TaggingService

            content_data = await process_course_for_tagging(str(course.id), session)
            if not content_data:
                logger.warning("Course %s not found or contains no content for tagging", course.id)
                return []

            tagging_service = TaggingService(session)
            tags = await tagging_service.tag_content(
                content_id=course.id,
                content_type="course",
                user_id=user_id,
                title=content_data.get("title", ""),
                content_preview=content_data.get("content_preview", ""),
            )

            if tags:
                course.tags = json.dumps(tags)
                await session.commit()

            return tags or []
        except Exception as exc:
            logger.exception("Auto-tagging error for course %s: %s", course.id, exc)
            return []

    async def _insert_lessons(
        self,
        session: AsyncSession,
        course_id: UUID,
        modules: list[dict[str, Any]],
    ) -> int:
        """Insert lessons for a course based on normalized module payload."""
        lesson_count = 0
        timestamp = datetime.now(UTC)

        for module_index, module in enumerate(modules):
            module_title = module.get("title")
            module_name = module_title.strip() if isinstance(module_title, str) and module_title.strip() else None
            module_order = module_index if module_name is not None else None
            raw_lessons = module.get("lessons", [])

            if not isinstance(raw_lessons, list):
                raw_lessons = [raw_lessons]

            for lesson_index, payload in enumerate(raw_lessons):
                if not isinstance(payload, dict):
                    continue

                title = payload.get("title") or f"Lesson {lesson_index + 1}"
                description = payload.get("description") or ""
                content = payload.get("content") or payload.get("body") or payload.get("markdown") or ""
                order_value = payload.get("order")
                lesson_order = int(order_value) if isinstance(order_value, int) else lesson_index

                lesson = Lesson(
                    course_id=course_id,
                    title=title,
                    description=description,
                    content=content,
                    order=lesson_order,
                    module_name=module_name,
                    module_order=module_order,
                    created_at=timestamp,
                    updated_at=timestamp,
                )
                session.add(lesson)
                lesson_count += 1

        return lesson_count

    def _normalize_modules_payload(
            self,
            modules: list[Any],
            lessons: list[Any],
        ) -> list[dict[str, Any]]:
        """Normalize modules/lessons with the simplest acceptable shape."""
        # Prefer explicit modules with a proper lessons list
        if isinstance(modules, list) and modules:
            normalized: list[dict[str, Any]] = []
            for module in modules:
                if not isinstance(module, dict):
                    continue
                ml = module.get("lessons")
                if isinstance(ml, list) and ml:
                    normalized.append(
                        {
                            "title": module.get("title"),
                            "description": module.get("description"),
                            "lessons": ml,
                        }
                    )
            if normalized:
                return normalized

        # Fallback: a flat lessons list becomes a single unnamed module
        if isinstance(lessons, list) and lessons:
            return [{"title": None, "description": None, "lessons": lessons}]

        # Nothing to insert
        return []


    def _ensure_json_string(self, value: Any) -> str:
        """Ensure value is serialized to a JSON string."""
        if isinstance(value, str):
            return value
        if isinstance(value, (list, tuple)):
            return json.dumps(list(value))
        try:
            return json.dumps(value)
        except Exception:
            return json.dumps(str(value))

    async def _generate_course_from_prompt(self, prompt: str, user_id: UUID) -> dict[str, Any]:
        """Generate course data from AI prompt."""
        ai_result = await self.ai_service.course_generate(user_id=user_id, topic=prompt)
        if not ai_result:
            error_msg = "Invalid AI response format for course generation"
            raise TypeError(error_msg)

        raw_course_data = ai_result.model_dump() if hasattr(ai_result, "model_dump") else ai_result
        course_data: dict[str, Any] = cast("dict[str, Any]", raw_course_data)

        title = course_data.get("title")
        description = course_data.get("description")
        if not title:
            error_msg = "AI generation returned no title"
            raise RuntimeError(error_msg)

        lessons = course_data.get("lessons", [])
        modules: list[dict[str, Any]] = []

        if isinstance(lessons, list) and lessons:
            module_map: dict[str, dict[str, Any]] = {}
            for lesson in lessons:
                if not isinstance(lesson, dict):
                    continue
                raw_module_name = lesson.get("module")
                module_name = raw_module_name.strip() if isinstance(raw_module_name, str) else None
                key = module_name or "__default__"
                module_entry = module_map.setdefault(
                    key,
                    {
                        "title": module_name,
                        "description": f"Learn about {module_name.lower()}" if module_name else None,
                        "lessons": [],
                    },
                )
                module_entry["lessons"].append(
                    {
                        "title": lesson.get("title", ""),
                        "description": lesson.get("description", ""),
                        "content": lesson.get("content") or lesson.get("body"),
                    }
                )

            modules = list(module_map.values())
        else:
            logger.warning("AI generated no lessons for prompt '%s'", prompt)

        result: dict[str, Any] = {
            "title": title,
            "description": description or f"A course about {prompt}",
            "tags": course_data.get("tags", []),
            "setup_commands": course_data.get("setup_commands", []),
            "modules": modules,
        }

        if course_data.get("archived") is not None:
            result["archived"] = course_data["archived"]

        return result
