"""Lesson service with SQL-first queries and mandatory user isolation."""

import logging
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai import AGENT_ID_LESSON_WRITER
from src.ai.client import LLMClient
from src.courses.models import Course, Lesson
from src.courses.schemas import LessonDetailResponse


logger = logging.getLogger(__name__)


class LessonService:
    """Lesson service with SQL-first queries and mandatory user isolation."""

    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        """Initialize with user context for security isolation."""
        self.session = session
        self.user_id = user_id

    async def _build_course_outline_context(
        self,
        *,
        course_id: UUID,
        lesson_id: UUID,
    ) -> tuple[list[dict[str, Any]], int | None, int | None, str | None]:
        outline_query = (
            select(
                Lesson.id,
                Lesson.title,
                Lesson.description,
            )
            .where(Lesson.course_id == course_id)
            .order_by(*Lesson.course_order_by())
        )

        outline_result = await self.session.execute(outline_query)
        rows = outline_result.all()

        ordered_lessons: list[dict[str, Any]] = []
        for row in rows:
            row_lesson_id, title, description = row
            ordered_lessons.append(
                {
                    "id": row_lesson_id,
                    "title": title,
                    "description": description,
                }
            )

        lesson_total = len(ordered_lessons)
        current_index = next((idx for idx, item in enumerate(ordered_lessons) if item.get("id") == lesson_id), None)
        if not isinstance(current_index, int):
            return [], None, lesson_total, None

        lesson_position = current_index + 1

        next_lesson_title: str | None = None
        next_item = ordered_lessons[current_index + 1] if current_index + 1 < lesson_total else None
        if isinstance(next_item, dict):
            next_title = next_item.get("title")
            if isinstance(next_title, str) and next_title.strip():
                next_lesson_title = next_title.strip()

        window_start = max(0, current_index - 2)
        window_end = min(lesson_total, current_index + 5)
        outline_window: list[dict[str, Any]] = []
        for idx in range(window_start, window_end):
            item = ordered_lessons[idx]
            title_value = item.get("title") or ""
            if not isinstance(title_value, str) or not title_value.strip():
                continue
            outline_window.append(
                {
                    "index": idx + 1,
                    "title": title_value,
                    "description": item.get("description") or "",
                }
            )

        return outline_window, lesson_position, lesson_total, next_lesson_title

    async def _build_rag_context(
        self,
        *,
        course_id: UUID,
        title: str,
        description: str,
    ) -> str:
        search_query = f"{title} {description}".strip()
        if not search_query:
            return ""

        try:
            from src.ai.rag.service import RAGService

            rag_service = RAGService()
            search_results = await rag_service.search_documents(
                session=self.session,
                user_id=self.user_id,
                course_id=course_id,
                query=search_query,
                top_k=5,
            )
            if not search_results:
                return ""

            context_parts = ["## Course Context"]
            for i, result in enumerate(search_results[:5], 1):
                context_parts.append(f"### Context {i}")
                context_parts.append(result.content)
                context_parts.append("")

            return "\n".join(context_parts).strip()
        except Exception:
            logger.exception(
                "Failed to get RAG context for course",
                extra={"user_id": str(self.user_id), "course_id": str(course_id)},
            )
            return ""

    def _build_outline_window_text(self, outline_window: list[dict[str, Any]]) -> str:
        if not outline_window:
            return ""

        outline_lines: list[str] = []
        for item in outline_window:
            index_value = item.get("index")
            title_value = item.get("title")
            if not isinstance(title_value, str) or not title_value:
                continue
            prefix = f"{index_value}. " if isinstance(index_value, int) else ""
            outline_lines.append(f"{prefix}{title_value}")

            item_desc = item.get("description")
            if isinstance(item_desc, str) and item_desc:
                outline_lines.append(f"Description: {item_desc}")
            outline_lines.append("")

        return "\n".join(outline_lines).strip()

    async def _prepare_lesson_context(
        self,
        *,
        lesson: Lesson,
        course: Course,
    ) -> str:
        outline_window: list[dict[str, Any]] = []
        lesson_position: int | None = None
        lesson_total: int | None = None
        next_lesson_title: str | None = None
        try:
            outline_window, lesson_position, lesson_total, next_lesson_title = await self._build_course_outline_context(
                course_id=course.id,
                lesson_id=lesson.id,
            )
        except Exception:
            logger.exception(
                "Failed to build course outline context",
                extra={"user_id": str(self.user_id), "course_id": str(course.id), "lesson_id": str(lesson.id)},
            )

        context_sections: list[str] = []

        course_lines: list[str] = [f"Course: {course.title}", "Course Description:", course.description]
        context_sections.append("## Course Information\n" + "\n".join(course_lines))

        lesson_lines: list[str] = []
        if lesson.module_name:
            lesson_lines.append(f"Module: {lesson.module_name}")
        if isinstance(lesson_position, int) and isinstance(lesson_total, int) and lesson_total > 0:
            lesson_lines.append(f"Current lesson: {lesson_position}/{lesson_total}")
        lesson_lines.append(f"Title: {lesson.title}")
        if lesson.description:
            lesson_lines.append("Description:")
            lesson_lines.append(lesson.description)
        context_sections.append("## Lesson Focus\n" + "\n".join(lesson_lines))

        if next_lesson_title:
            context_sections.append("## Next Lesson\n" + f"Next: {next_lesson_title}")

        outline_text = self._build_outline_window_text(outline_window)
        if outline_text:
            context_sections.append("## Course Outline (Near Term)\n" + outline_text)

        rag_context = await self._build_rag_context(
            course_id=course.id,
            title=lesson.title,
            description=lesson.description or "",
        )
        return "\n\n".join([*context_sections, rag_context]).strip()

    async def _generate_lesson_body(self, *, lesson_context: str) -> str:
        llm_client = LLMClient(agent_id=AGENT_ID_LESSON_WRITER)
        lesson_content = await llm_client.generate_lesson_content(lesson_context, user_id=self.user_id)
        return lesson_content.body

    async def get_lesson(
        self,
        course_id: UUID,
        lesson_id: UUID,
        force_refresh: bool = False,
    ) -> LessonDetailResponse:
        """Get lesson with single query including user isolation.

        Args:
            course_id: Course UUID
            lesson_id: Lesson UUID
            force_refresh: Whether to regenerate content even if it already exists

        Returns
        -------
            LessonDetailResponse containing lesson data

        Raises
        ------
            HTTPException: 404 if lesson not found or access denied
        """
        # Single query with USER ISOLATION - prevents data leakage
        query = (
            select(Lesson, Course)
            .join(Course, Lesson.course_id == Course.id)
            .where(
                Lesson.id == lesson_id,
                Lesson.course_id == course_id,
                Course.user_id == self.user_id,
            )
        )
        result = await self.session.execute(query)
        row = result.first()

        if not row:
            # Log security event with user context
            logger.warning(
                "LESSON_ACCESS_DENIED",
                extra={"user_id": str(self.user_id), "lesson_id": str(lesson_id), "course_id": str(course_id)},
            )
            raise HTTPException(status_code=404, detail="Lesson not found or access denied")

        lesson, course = row

        if force_refresh or lesson.content == "":
            lesson = await self._ensure_lesson_content(lesson, course, force_refresh=force_refresh)

        concept_id_value = getattr(cast("Any", lesson), "concept_id", None)

        return LessonDetailResponse(
            id=lesson.id,
            course_id=course.id,
            title=lesson.title,
            description=lesson.description,
            content=lesson.content,
            concept_id=concept_id_value,
            adaptive_enabled=course.adaptive_enabled,
            created_at=lesson.created_at,
            updated_at=lesson.updated_at,
        )

    async def _ensure_lesson_content(self, lesson: Lesson, course: Course, force_refresh: bool = False) -> Lesson:
        """Generate content for a lesson on demand."""
        if not force_refresh and lesson.content != "":
            return lesson

        try:
            logger.info(
                "Generating lesson content",
                extra={
                    "user_id": str(self.user_id),
                    "lesson_id": str(lesson.id),
                    "lesson_title": lesson.title,
                },
            )
            lesson_context = await self._prepare_lesson_context(lesson=lesson, course=course)
            content = await self._generate_lesson_body(lesson_context=lesson_context)

            conditions = [Lesson.id == lesson.id]
            if not force_refresh:
                conditions.append(Lesson.content == "")

            update_stmt = update(Lesson).where(*conditions).values(content=content, updated_at=datetime.now(UTC))

            update_result = await self.session.execute(update_stmt)
            updated_rows = getattr(update_result, "rowcount", None)

            if updated_rows and updated_rows > 0:
                await self.session.flush()
                await self.session.refresh(lesson)
                logger.info(
                    "Lesson content generated and saved",
                    extra={
                        "user_id": str(self.user_id),
                        "lesson_id": str(lesson.id),
                        "content_length": len(content) if content else 0,
                    },
                )
            else:
                logger.info(
                    "Content already generated by another process",
                    extra={"user_id": str(self.user_id), "lesson_id": str(lesson.id)},
                )
                await self.session.refresh(lesson)

        except ValueError as exc:
            logger.exception(
                "Validation error generating lesson content: %s",
                str(exc),
                extra={"user_id": str(self.user_id), "lesson_id": str(lesson.id)},
            )
            raise HTTPException(status_code=400, detail=f"Invalid lesson content: {exc}") from exc
        except RuntimeError as exc:
            logger.exception(
                "System error generating lesson content: %s",
                str(exc),
                extra={"user_id": str(self.user_id), "lesson_id": str(lesson.id)},
            )
            raise HTTPException(status_code=503, detail="Unable to generate lesson content. Please try again.") from exc
        except Exception as exc:
            logger.exception(
                "Unexpected error generating lesson content",
                extra={"user_id": str(self.user_id), "lesson_id": str(lesson.id)},
            )
            raise HTTPException(
                status_code=500, detail="An unexpected error occurred while generating lesson content"
            ) from exc

        return lesson
