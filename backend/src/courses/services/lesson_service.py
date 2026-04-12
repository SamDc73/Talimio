
import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession


"""Lesson service with SQL-first queries and mandatory user isolation."""


import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

from src.ai import AGENT_ID_LESSON_WRITER
from src.ai.client import LLMClient
from src.courses.models import Concept, Course, CourseConcept, Lesson, LessonVersion, ProbeEvent, UserConceptState
from src.courses.schemas import (
    LessonDetailResponse,
    LessonVersionHistoryResponse,
    LessonVersionSummary,
    LessonWindowResponse,
)
from src.courses.services.lesson_version_service import LessonVersionService
from src.courses.services.lesson_window_service import LessonWindowService
from src.exceptions import NotFoundError, UpstreamUnavailableError, ValidationError


logger = logging.getLogger(__name__)

_LESSON_RAG_CONTEXT_FALLBACK_ERROR_TYPES = (
    ImportError,
    SQLAlchemyError,
    RuntimeError,
    TypeError,
    ValueError,
    OSError,
    ConnectionError,
    TimeoutError,
)
_LESSON_OUTLINE_FALLBACK_ERROR_TYPES = (
    SQLAlchemyError,
    RuntimeError,
    TypeError,
    ValueError,
)
_LESSON_GENERATION_HTTP_500_ERROR_TYPES = (
    SQLAlchemyError,
    OSError,
    TypeError,
    ConnectionError,
    TimeoutError,
)
_LESSON_LEARNER_STATE_FALLBACK_ERROR_TYPES = (SQLAlchemyError,)


class LessonService:
    """Lesson service with SQL-first queries and mandatory user isolation."""

    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        """Initialize with user context for security isolation."""
        self.session = session
        self.user_id = user_id

    async def _load_owned_lesson_and_course(
        self,
        *,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> tuple[Lesson, Course]:
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
            logger.warning(
                "LESSON_ACCESS_DENIED",
                extra={"user_id": str(self.user_id), "lesson_id": str(lesson_id), "course_id": str(course_id)},
            )
            raise NotFoundError(
                message="Lesson not found or access denied",
                feature_area="courses",
            )

        lesson, course = row
        return lesson, course

    async def _build_course_outline_context(
        self,
        *,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> tuple[list[dict[str, Any]], int | None, int | None, str | None]:
        rows = (
            await self.session.execute(
                select(
                    Lesson.id,
                    Lesson.title,
                    Lesson.description,
                )
                .where(Lesson.course_id == course_id)
                .order_by(*Lesson.course_order_by())
            )
        ).all()

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
        next_lesson_title = self._resolve_next_lesson_title(ordered_lessons, current_index)

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

    def _resolve_next_lesson_title(self, ordered_lessons: list[dict[str, Any]], current_index: int) -> str | None:
        next_index = current_index + 1
        if next_index >= len(ordered_lessons):
            return None
        next_title = ordered_lessons[next_index].get("title")
        if isinstance(next_title, str) and next_title.strip():
            return next_title.strip()
        return None

    def _resolve_concept_id_for_lesson(
        self,
        *,
        lesson_id: uuid.UUID,
        course_id: uuid.UUID,
        concept_ids: Sequence[uuid.UUID],
    ) -> uuid.UUID | None:
        for concept_id in concept_ids:
            candidate = uuid.uuid5(uuid.NAMESPACE_URL, f"concept-lesson:{course_id}:{concept_id}")
            if candidate == lesson_id:
                return concept_id
        return None

    async def _get_course_concept_ids(self, *, course_id: uuid.UUID) -> list[uuid.UUID]:
        return (
            (
                await self.session.execute(
                    select(CourseConcept.concept_id)
                    .where(CourseConcept.course_id == course_id)
                    .order_by(CourseConcept.order_hint.asc().nulls_last(), CourseConcept.concept_id.asc())
                )
            )
            .scalars()
            .all()
        )

    async def _get_lesson_concept_id(self, *, course_id: uuid.UUID, lesson_id: uuid.UUID) -> uuid.UUID | None:
        concept_ids = await self._get_course_concept_ids(course_id=course_id)
        if not concept_ids:
            return None
        return self._resolve_concept_id_for_lesson(
            lesson_id=lesson_id,
            course_id=course_id,
            concept_ids=concept_ids,
        )

    async def _build_adaptive_learner_state_context(
        self,
        *,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> str | None:
        concept_id = await self._get_lesson_concept_id(course_id=course_id, lesson_id=lesson_id)
        if concept_id is None:
            return None

        concept_name = await self.session.scalar(select(Concept.name).where(Concept.id == concept_id))
        if not isinstance(concept_name, str) or not concept_name.strip():
            return None

        state = await self.session.scalar(
            select(UserConceptState).where(
                UserConceptState.user_id == self.user_id,
                UserConceptState.concept_id == concept_id,
            )
        )
        outcomes = (
            (
                await self.session.execute(
                    select(ProbeEvent.correct)
                    .where(
                        ProbeEvent.user_id == self.user_id,
                        ProbeEvent.concept_id == concept_id,
                    )
                    .order_by(ProbeEvent.ts.desc())
                    .limit(5)
                )
            )
            .scalars()
            .all()
        )

        lines = ["## Learner State", f"Concept: {concept_name.strip()}"]
        if state is None and not outcomes:
            return None

        if state is not None:
            mastery = float(state.s_mastery)
            lines.append(f"Mastery: {mastery:.2f}")

            if state.exposures > 0:
                lines.append(f"Exposures: {state.exposures}")

            if isinstance(state.learner_profile, dict):
                retention_raw = state.learner_profile.get("retention_rate")
                if isinstance(retention_raw, (int, float)):
                    lines.append(f"Retention: {float(retention_raw):.2f}")

            if state.next_review_at is not None:
                next_review_at = state.next_review_at
                if next_review_at.tzinfo is None:
                    next_review_at = next_review_at.replace(tzinfo=UTC)
                review_status = "overdue" if next_review_at < datetime.now(UTC) else "on schedule"
                lines.append(f"Review due: {review_status}")

        if outcomes:
            recent_correct = sum(1 for outcome in outcomes if outcome)
            lines.append(f"Recent probes: {recent_correct}/{len(outcomes)} correct")

        return "\n".join(lines)

    async def _build_rag_context(
        self,
        *,
        course_id: uuid.UUID,
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
        except _LESSON_RAG_CONTEXT_FALLBACK_ERROR_TYPES:
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
        except _LESSON_OUTLINE_FALLBACK_ERROR_TYPES:
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
        context_sections.append(LessonWindowService(self.session).build_generation_context(course=course))

        if next_lesson_title:
            context_sections.append("## Next Lesson\n" + f"Next: {next_lesson_title}")

        outline_text = self._build_outline_window_text(outline_window)
        if outline_text:
            context_sections.append("## Course Outline (Near Term)\n" + outline_text)

        if course.adaptive_enabled:
            try:
                learner_state_context = await self._build_adaptive_learner_state_context(
                    course_id=course.id,
                    lesson_id=lesson.id,
                )
                if learner_state_context:
                    context_sections.append(learner_state_context)
            except _LESSON_LEARNER_STATE_FALLBACK_ERROR_TYPES:
                logger.exception(
                    "Failed to build adaptive learner state context",
                    extra={"user_id": str(self.user_id), "course_id": str(course.id), "lesson_id": str(lesson.id)},
                )

        rag_context = await self._build_rag_context(
            course_id=course.id,
            title=lesson.title,
            description=lesson.description or "",
        )
        return "\n\n".join([*context_sections, rag_context]).strip()

    async def _prepare_regeneration_context(
        self,
        *,
        lesson: Lesson,
        course: Course,
        critique_text: str,
    ) -> str:
        lesson_context = await self._prepare_lesson_context(lesson=lesson, course=course)
        return "\n\n".join([lesson_context, f"## Regeneration Request\n{critique_text}"]).strip()

    async def _generate_lesson_body(self, *, lesson_context: str) -> str:
        llm_client = LLMClient(agent_id=AGENT_ID_LESSON_WRITER)
        lesson_content = await llm_client.generate_lesson_content(lesson_context, user_id=self.user_id)
        return lesson_content.body

    def _build_version_summaries(
        self,
        *,
        lesson: Lesson,
        versions: Sequence[LessonVersion],
    ) -> list[LessonVersionSummary]:
        return [
            LessonVersionSummary(
                id=version.id,
                major_version=version.major_version,
                minor_version=version.minor_version,
                version_kind=version.version_kind,
                version_label=f"{version.major_version}.{version.minor_version}",
                is_current=version.id == lesson.current_version_id,
                created_at=version.created_at,
            )
            for version in versions
        ]

    def _build_window_payload(self, windows: Sequence[Any]) -> list[LessonWindowResponse]:
        return [
            LessonWindowResponse(
                id=window.id,
                window_index=window.window_index,
                title=window.title,
                content=window.content,
                estimated_minutes=window.estimated_minutes,
            )
            for window in windows
        ]

    async def _build_lesson_detail_response(
        self,
        *,
        lesson: Lesson,
        course: Course,
        selected_version: LessonVersion,
        available_versions: Sequence[LessonVersion],
        windows: Sequence[Any],
    ) -> LessonDetailResponse:
        concept_id_value = await self._get_lesson_concept_id(course_id=course.id, lesson_id=lesson.id)
        return LessonDetailResponse(
            id=lesson.id,
            course_id=course.id,
            title=lesson.title,
            description=lesson.description,
            content=selected_version.content,
            concept_id=concept_id_value,
            version_id=selected_version.id,
            current_version_id=lesson.current_version_id,
            major_version=selected_version.major_version,
            minor_version=selected_version.minor_version,
            version_kind=selected_version.version_kind,
            available_versions=self._build_version_summaries(lesson=lesson, versions=available_versions),
            windows=self._build_window_payload(windows),
            adaptive_enabled=course.adaptive_enabled,
            created_at=lesson.created_at,
            updated_at=lesson.updated_at,
        )

    async def get_lesson(
        self,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
        force_refresh: bool = False,
        version_id: uuid.UUID | None = None,
    ) -> LessonDetailResponse:
        """Get lesson with single query including user isolation.

        Args:
            course_id: Course uuid.UUID
            lesson_id: Lesson uuid.UUID
            force_refresh: Whether to regenerate content even if it already exists
            version_id: Optional version row to read through the same lesson route

        Returns
        -------
            LessonDetailResponse containing lesson data

        Raises
        ------
            NotFoundError: If the lesson is missing or not owned by the current user
        """
        lesson, course = await self._load_owned_lesson_and_course(course_id=course_id, lesson_id=lesson_id)

        if force_refresh or lesson.content == "":
            lesson = await self._ensure_lesson_content(lesson, course, force_refresh=force_refresh)

        lesson_version_service = LessonVersionService(self.session)
        lesson_window_service = LessonWindowService(self.session)
        current_version = await lesson_version_service.sync_current_version_from_lesson(lesson=lesson)
        selected_version = current_version
        if version_id is not None and version_id != current_version.id:
            selected_version = await lesson_version_service.get_version(lesson=lesson, version_id=version_id)
        available_versions = await lesson_version_service.list_versions(lesson=lesson)
        selected_windows = await lesson_window_service.get_or_build_windows(lesson_version=selected_version)

        return await self._build_lesson_detail_response(
            lesson=lesson,
            course=course,
            selected_version=selected_version,
            available_versions=available_versions,
            windows=selected_windows,
        )

    async def list_lesson_versions(
        self,
        *,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> LessonVersionHistoryResponse:
        """Return stable version history for one lesson."""
        lesson, course = await self._load_owned_lesson_and_course(course_id=course_id, lesson_id=lesson_id)
        if lesson.content == "":
            lesson = await self._ensure_lesson_content(lesson, course)

        lesson_version_service = LessonVersionService(self.session)
        await lesson_version_service.sync_current_version_from_lesson(lesson=lesson)
        versions = await lesson_version_service.list_versions(lesson=lesson)
        return LessonVersionHistoryResponse(versions=self._build_version_summaries(lesson=lesson, versions=versions))

    async def regenerate_lesson(
        self,
        *,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
        critique_text: str,
    ) -> LessonDetailResponse:
        """Regenerate an existing lesson body using the normal writer path plus learner critique."""
        lesson, course = await self._load_owned_lesson_and_course(course_id=course_id, lesson_id=lesson_id)

        trimmed_critique = critique_text.strip()
        if not trimmed_critique:
            detail = "Regeneration request must not be empty"
            raise ValidationError(detail, feature_area="courses")

        try:
            lesson_version_service = LessonVersionService(self.session)
            lesson_window_service = LessonWindowService(self.session)
            lesson_context = await self._prepare_regeneration_context(
                lesson=lesson,
                course=course,
                critique_text=trimmed_critique,
            )
            generated_content = await self._generate_lesson_body(lesson_context=lesson_context)
            selected_version = await lesson_version_service.create_regenerated_version(
                lesson=lesson,
                content=generated_content,
                critique_text=trimmed_critique,
            )
            selected_windows = await lesson_window_service.rebuild_windows(lesson_version=selected_version)
            await self.session.refresh(lesson)
        except ValueError as exc:
            detail = f"Invalid lesson content: {exc}"
            raise ValidationError(detail, feature_area="courses") from exc
        except RuntimeError as exc:
            message = "Unable to generate lesson content. Please try again."
            raise UpstreamUnavailableError(message, feature_area="courses") from exc

        available_versions = await lesson_version_service.list_versions(lesson=lesson)
        return await self._build_lesson_detail_response(
            lesson=lesson,
            course=course,
            selected_version=selected_version,
            available_versions=available_versions,
            windows=selected_windows,
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
            detail = f"Invalid lesson content: {exc}"
            raise ValidationError(detail, feature_area="courses") from exc
        except RuntimeError as exc:
            message = "Unable to generate lesson content. Please try again."
            raise UpstreamUnavailableError(message, feature_area="courses") from exc
        return lesson
