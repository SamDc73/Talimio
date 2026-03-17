"""Write-side learning capability service."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai import AGENT_ID_LESSON_WRITER
from src.courses.facade import CoursesFacade
from src.courses.models import Course, Lesson
from src.courses.services.lesson_service import LessonService
from src.learning_capabilities.errors import LearningCapabilitiesValidationError
from src.learning_capabilities.schemas import (
    AppendCourseLessonCapabilityInput,
    AppendCourseLessonCapabilityOutput,
    CreateCourseCapabilityInput,
    CreateCourseCapabilityOutput,
    ExtendLessonWithContextCapabilityInput,
    LessonMutationCapabilityOutput,
    RegenerateLessonWithContextCapabilityInput,
    ToolUiConfirmation,
    ToolUiLink,
)
from src.learning_capabilities.services.authorization_service import LearningCapabilityAuthorizationService


logger = logging.getLogger(__name__)


class LearningCapabilityActionService:
    """Capability-backed write operations for course/lesson mutations."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        authorization_service: LearningCapabilityAuthorizationService,
    ) -> None:
        self._session = session
        self._authorization_service = authorization_service

    async def create_course(
        self,
        *,
        user_id: uuid.UUID,
        payload: CreateCourseCapabilityInput,
    ) -> CreateCourseCapabilityOutput:
        """Create a new course from a learner prompt."""
        if not payload.confirmed:
            return _build_create_confirmation()

        facade = CoursesFacade(self._session)
        created_course = await facade.create_course(
            {"prompt": payload.prompt.strip(), "adaptive_enabled": payload.adaptive_enabled},
            user_id=user_id,
        )

        result = CreateCourseCapabilityOutput(
            status="completed",
            message="Course created.",
            course_id=created_course.id,
            title=created_course.title,
            tool_ui=[
                ToolUiLink(
                    label="Open course",
                    href=f"/course/{created_course.id}",
                )
            ],
        )
        _log_mutation(
            capability_name="create_course",
            user_id=user_id,
            payload=payload.model_dump(mode="json"),
            result=result.model_dump(mode="json"),
        )
        return result

    async def append_course_lesson(
        self,
        *,
        user_id: uuid.UUID,
        payload: AppendCourseLessonCapabilityInput,
    ) -> AppendCourseLessonCapabilityOutput:
        """Append one lesson row to an owned course and optionally generate content."""
        if not payload.confirmed:
            return _build_append_confirmation(payload)

        course = await self._authorization_service.require_owned_course(
            user_id=user_id,
            course_id=payload.course_id,
        )
        normalized_module_name = _normalize_optional_text(payload.module_name)
        next_order = await self._resolve_next_lesson_order(course_id=course.id)
        module_order = await self._resolve_module_order(course_id=course.id, module_name=normalized_module_name)

        lesson = Lesson(
            course_id=course.id,
            title=payload.lesson_title.strip(),
            description=_normalize_optional_text(payload.lesson_description),
            content="",
            order=next_order,
            module_name=normalized_module_name,
            module_order=module_order,
            updated_at=datetime.now(UTC),
        )
        self._session.add(lesson)
        await self._session.flush()

        content_generated = False
        if payload.generate_content:
            lesson_service = LessonService(self._session, user_id)
            detail = await lesson_service.get_lesson(course.id, lesson.id, force_refresh=True)
            content_generated = bool(detail.content and detail.content.strip())
            lesson.title = detail.title

        result = AppendCourseLessonCapabilityOutput(
            status="completed",
            message="Lesson appended.",
            course_id=course.id,
            lesson_id=lesson.id,
            lesson_title=lesson.title,
            content_generated=content_generated,
            tool_ui=[
                ToolUiLink(
                    label=_OPEN_LESSON_LABEL,
                    href=f"/course/{course.id}/lesson/{lesson.id}",
                )
            ],
        )
        _log_mutation(
            capability_name="append_course_lesson",
            user_id=user_id,
            payload=payload.model_dump(mode="json"),
            result=result.model_dump(mode="json"),
        )
        return result

    async def extend_lesson_with_context(
        self,
        *,
        user_id: uuid.UUID,
        payload: ExtendLessonWithContextCapabilityInput,
    ) -> LessonMutationCapabilityOutput:
        """Append generated content to the current lesson body."""
        if not payload.confirmed:
            return _build_extend_confirmation(payload)

        course, lesson = await self._authorization_service.require_owned_lesson(
            user_id=user_id,
            course_id=payload.course_id,
            lesson_id=payload.lesson_id,
        )
        generated_content = await self._generate_lesson_content(
            user_id=user_id,
            course=course,
            lesson=lesson,
            extra_context=payload.context,
            mode="append",
        )

        normalized_generated = generated_content.strip()
        existing_content = (lesson.content or "").rstrip()
        lesson.content = f"{existing_content}\n\n---\n\n{normalized_generated}" if existing_content else normalized_generated
        lesson.updated_at = datetime.now(UTC)
        await self._session.flush()

        result = LessonMutationCapabilityOutput(
            status="completed",
            message="Lesson extended.",
            course_id=course.id,
            lesson_id=lesson.id,
            lesson_title=lesson.title,
            has_content=bool(lesson.content and lesson.content.strip()),
            tool_ui=[
                ToolUiLink(
                    label=_OPEN_LESSON_LABEL,
                    href=f"/course/{course.id}/lesson/{lesson.id}",
                )
            ],
        )
        _log_mutation(
            capability_name="extend_lesson_with_context",
            user_id=user_id,
            payload=payload.model_dump(mode="json"),
            result=result.model_dump(mode="json"),
        )
        return result

    async def regenerate_lesson_with_context(
        self,
        *,
        user_id: uuid.UUID,
        payload: RegenerateLessonWithContextCapabilityInput,
    ) -> LessonMutationCapabilityOutput:
        """Replace lesson content with a regenerated body using injected context."""
        if not payload.confirmed:
            return _build_regenerate_confirmation(payload)

        course, lesson = await self._authorization_service.require_owned_lesson(
            user_id=user_id,
            course_id=payload.course_id,
            lesson_id=payload.lesson_id,
        )
        regenerated_content = await self._generate_lesson_content(
            user_id=user_id,
            course=course,
            lesson=lesson,
            extra_context=payload.context,
            mode="replace",
        )

        lesson.content = regenerated_content.strip()
        lesson.updated_at = datetime.now(UTC)
        await self._session.flush()

        result = LessonMutationCapabilityOutput(
            status="completed",
            message="Lesson regenerated.",
            course_id=course.id,
            lesson_id=lesson.id,
            lesson_title=lesson.title,
            has_content=bool(lesson.content and lesson.content.strip()),
            tool_ui=[
                ToolUiLink(
                    label=_OPEN_LESSON_LABEL,
                    href=f"/course/{course.id}/lesson/{lesson.id}",
                )
            ],
        )
        _log_mutation(
            capability_name="regenerate_lesson_with_context",
            user_id=user_id,
            payload=payload.model_dump(mode="json"),
            result=result.model_dump(mode="json"),
        )
        return result

    async def _resolve_next_lesson_order(self, *, course_id: uuid.UUID) -> int:
        max_order = await self._session.scalar(
            select(func.max(Lesson.order)).where(Lesson.course_id == course_id)
        )
        return int(max_order or 0) + 1

    async def _resolve_module_order(self, *, course_id: uuid.UUID, module_name: str | None) -> int | None:
        if module_name is None:
            return None

        existing = await self._session.scalar(
            select(Lesson.module_order).where(
                Lesson.course_id == course_id,
                Lesson.module_name == module_name,
                Lesson.module_order.is_not(None),
            )
        )
        if isinstance(existing, int):
            return existing

        max_module_order = await self._session.scalar(
            select(func.max(Lesson.module_order)).where(
                Lesson.course_id == course_id,
                Lesson.module_order.is_not(None),
            )
        )
        return int(max_module_order or 0) + 1

    async def _generate_lesson_content(
        self,
        *,
        user_id: uuid.UUID,
        course: Course,
        lesson: Lesson,
        extra_context: str,
        mode: str,
    ) -> str:
        context_text = extra_context.strip()
        if not context_text:
            detail = "Context is required for lesson mutation."
            raise LearningCapabilitiesValidationError(detail)

        lesson_service = LessonService(self._session, user_id)
        base_context = await lesson_service._prepare_lesson_context(lesson=lesson, course=course)  # noqa: SLF001
        mode_instruction = (
            "Extend the current lesson with new material that continues the existing flow."
            if mode == "append"
            else "Regenerate the full lesson body from scratch while respecting the course context."
        )

        lesson_content = (lesson.content or "").strip() or "[No existing lesson body]"
        composed_context = "\n\n".join(
            [
                base_context,
                "## Current Lesson Body\n" + lesson_content,
                "## Injected Context\n" + context_text,
                "## Task\n" + mode_instruction,
            ]
        )
        from src.ai.client import LLMClient

        llm_client = LLMClient(agent_id=AGENT_ID_LESSON_WRITER)
        generated = await llm_client.generate_lesson_content(composed_context, user_id=user_id)
        return generated.body


_OPEN_LESSON_LABEL = "Open lesson"


def _log_mutation(
    *,
    capability_name: str,
    user_id: uuid.UUID,
    payload: dict[str, object],
    result: dict[str, object],
) -> None:
    status = result.get("status")
    course_id = result.get("course_id") or payload.get("course_id")
    lesson_id = result.get("lesson_id") or payload.get("lesson_id")
    logger.info(
        "learning_capability.mutation",
        extra={
            "capability_name": capability_name,
            "user_id": str(user_id),
            "status": status,
            "course_id": str(course_id) if course_id is not None else None,
            "lesson_id": str(lesson_id) if lesson_id is not None else None,
        },
    )


def _normalize_optional_text(raw: str | None) -> str | None:
    if raw is None:
        return None
    normalized = raw.strip()
    return normalized or None


def _build_create_confirmation() -> CreateCourseCapabilityOutput:
    return CreateCourseCapabilityOutput(
        status="confirmation_required",
        message="Creating a new course will add content to your account.",
        tool_ui=[
            ToolUiConfirmation(
                title="Create course?",
                message="This will create a new course using your prompt.",
                action_name="create_course",
            )
        ],
    )


def _build_append_confirmation(payload: AppendCourseLessonCapabilityInput) -> AppendCourseLessonCapabilityOutput:
    return AppendCourseLessonCapabilityOutput(
        status="confirmation_required",
        message="Appending a lesson will mutate the course outline.",
        course_id=payload.course_id,
        lesson_title=payload.lesson_title,
        tool_ui=[
            ToolUiConfirmation(
                title="Append lesson?",
                message=f"This will add '{payload.lesson_title.strip()}' to the course.",
                action_name="append_course_lesson",
            )
        ],
    )


def _build_extend_confirmation(payload: ExtendLessonWithContextCapabilityInput) -> LessonMutationCapabilityOutput:
    return LessonMutationCapabilityOutput(
        status="confirmation_required",
        message="Extending the lesson will append newly generated content.",
        course_id=payload.course_id,
        lesson_id=payload.lesson_id,
        tool_ui=[
            ToolUiConfirmation(
                title="Extend lesson?",
                message="This will append generated content to the current lesson body.",
                action_name="extend_lesson_with_context",
            )
        ],
    )


def _build_regenerate_confirmation(payload: RegenerateLessonWithContextCapabilityInput) -> LessonMutationCapabilityOutput:
    return LessonMutationCapabilityOutput(
        status="confirmation_required",
        message="Regeneration replaces the current lesson content.",
        course_id=payload.course_id,
        lesson_id=payload.lesson_id,
        tool_ui=[
            ToolUiConfirmation(
                title="Regenerate lesson?",
                message="This will replace the current lesson body.",
                action_name="regenerate_lesson_with_context",
            )
        ],
    )
