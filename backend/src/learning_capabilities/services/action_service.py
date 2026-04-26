"""Write-side learning capability service."""

import logging
import uuid
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai import AGENT_ID_LESSON_WRITER
from src.ai.assistant.models import AssistantActiveProbe, AssistantConversation
from src.ai.errors import AIRuntimeError
from src.ai.tools.wikipedia import build_wikipedia_resolver_function_tool
from src.courses.facade import CoursesFacade
from src.courses.models import Course, Lesson
from src.courses.schemas import (
    GradeAnswerPayload,
    GradeContextPayload,
    GradeExpectedPayload,
    GradeRequest,
    PracticeAnswerKind,
)
from src.courses.services.concept_scheduler_service import LectorSchedulerService
from src.courses.services.concept_state_service import ConceptStateService
from src.courses.services.grading_service import GradingService
from src.courses.services.lesson_service import LessonService
from src.courses.services.practice_drill_service import PracticeDrillService
from src.learning_capabilities.errors import LearningCapabilitiesValidationError
from src.learning_capabilities.schemas import (
    AppendCourseLessonCapabilityInput,
    AppendCourseLessonCapabilityOutput,
    ChatConceptProbe,
    CourseMode,
    CreateCourseCapabilityInput,
    CreateCourseCapabilityOutput,
    ExtendLessonWithContextCapabilityInput,
    GenerateConceptProbeCapabilityInput,
    GenerateConceptProbeCapabilityOutput,
    LessonMutationCapabilityOutput,
    RegenerateLessonWithContextCapabilityInput,
    SubmitConceptProbeResultCapabilityInput,
    SubmitConceptProbeResultCapabilityOutput,
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

    async def generate_concept_probe(  # noqa: PLR0911, PLR0912
        self,
        *,
        user_id: uuid.UUID,
        payload: GenerateConceptProbeCapabilityInput,
    ) -> GenerateConceptProbeCapabilityOutput:
        """Generate one learner-visible chat probe while storing hidden grading state."""
        course = await self._authorization_service.require_owned_course(
            user_id=user_id,
            course_id=payload.course_id,
        )
        course_mode: CourseMode = "adaptive" if course.adaptive_enabled else "standard"
        if not course.adaptive_enabled:
            return GenerateConceptProbeCapabilityOutput(
                course_id=course.id,
                course_mode=course_mode,
                concept_id=payload.concept_id,
                reason="standard_course_has_no_concept_graph",
            )

        conversation_id = await self._resolve_owned_thread_id(
            user_id=user_id,
            thread_id=payload.thread_id,
            course_id=course.id,
        )

        if payload.lesson_id is not None:
            lesson_matches_concept = await self._lesson_matches_concept(
                course_id=course.id,
                lesson_id=payload.lesson_id,
                concept_id=payload.concept_id,
            )
            if not lesson_matches_concept:
                return GenerateConceptProbeCapabilityOutput(
                    course_id=course.id,
                    course_mode=course_mode,
                    concept_id=payload.concept_id,
                    reason="concept_not_assigned_to_current_lesson",
                )
            existing_lesson_probe = await self._get_active_probe_for_lesson(
                user_id=user_id,
                conversation_id=conversation_id,
                course_id=course.id,
                lesson_id=payload.lesson_id,
                concept_id=payload.concept_id,
            )
            if existing_lesson_probe is not None:
                return _active_probe_output(course=course, course_mode=course_mode, active_probe=existing_lesson_probe)
        else:
            existing_probe = await self._get_active_probe(
                user_id=user_id,
                conversation_id=conversation_id,
                course_id=course.id,
                concept_id=payload.concept_id,
            )
            if existing_probe is not None:
                return _active_probe_output(course=course, course_mode=course_mode, active_probe=existing_probe)

        service = PracticeDrillService(self._session)
        try:
            drill = (
                await service.generate_drills(
                    user_id=user_id,
                    course_id=course.id,
                    concept_id=payload.concept_id,
                    count=payload.count,
                    learner_context=payload.learner_context,
                )
            )[0]
        except LookupError as error:
            return GenerateConceptProbeCapabilityOutput(
                course_id=course.id,
                course_mode=course_mode,
                concept_id=payload.concept_id,
                reason=_probe_lookup_reason(error),
            )
        except (AIRuntimeError, RuntimeError, TypeError, ValueError, OSError):
            logger.warning(
                "learning_capability.generate_concept_probe.unavailable",
                extra={"user_id": str(user_id), "course_id": str(course.id), "concept_id": str(payload.concept_id)},
                exc_info=True,
            )
            return GenerateConceptProbeCapabilityOutput(
                course_id=course.id,
                course_mode=course_mode,
                concept_id=payload.concept_id,
                reason="probe_generation_unavailable",
            )
        if payload.lesson_id is not None and drill.lesson_id != payload.lesson_id:
            return GenerateConceptProbeCapabilityOutput(
                course_id=course.id,
                course_mode=course_mode,
                concept_id=payload.concept_id,
                reason="concept_not_assigned_to_current_lesson",
            )

        active_probe = AssistantActiveProbe(
            user_id=user_id,
            conversation_id=conversation_id,
            course_id=course.id,
            concept_id=drill.concept_id,
            lesson_id=drill.lesson_id,
            question=drill.question,
            expected_answer=drill.expected_answer,
            answer_kind=drill.answer_kind,
            hints=list(drill.hints),
            structure_signature=drill.structure_signature,
            predicted_p_correct=drill.predicted_p_correct,
            target_probability=drill.target_probability,
            target_low=drill.target_low,
            target_high=drill.target_high,
            core_model=drill.core_model,
            practice_context=payload.practice_context,
        )
        self._session.add(active_probe)
        try:
            await self._session.flush()
        except IntegrityError:
            await self._session.rollback()
            if payload.lesson_id is not None:
                existing_lesson_probe = await self._get_active_probe_for_lesson(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    course_id=course.id,
                    lesson_id=payload.lesson_id,
                    concept_id=payload.concept_id,
                )
                if existing_lesson_probe is not None:
                    return _active_probe_output(course=course, course_mode=course_mode, active_probe=existing_lesson_probe)
            else:
                existing_probe = await self._get_active_probe(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    course_id=course.id,
                    concept_id=payload.concept_id,
                )
                if existing_probe is not None:
                    return _active_probe_output(course=course, course_mode=course_mode, active_probe=existing_probe)
            logger.warning(
                "learning_capability.generate_concept_probe.persist_failed",
                extra={"user_id": str(user_id), "course_id": str(course.id), "concept_id": str(payload.concept_id)},
                exc_info=True,
            )
            return GenerateConceptProbeCapabilityOutput(
                course_id=course.id,
                course_mode=course_mode,
                concept_id=payload.concept_id,
                reason="probe_generation_unavailable",
            )

        return _active_probe_output(course=course, course_mode=course_mode, active_probe=active_probe)

    async def submit_concept_probe_result(
        self,
        *,
        user_id: uuid.UUID,
        payload: SubmitConceptProbeResultCapabilityInput,
    ) -> SubmitConceptProbeResultCapabilityOutput:
        """Grade and record one answer to an active chat-generated probe."""
        course = await self._authorization_service.require_owned_course(user_id=user_id, course_id=payload.course_id)
        course_mode: CourseMode = "adaptive" if course.adaptive_enabled else "standard"
        if not course.adaptive_enabled:
            return SubmitConceptProbeResultCapabilityOutput(
                course_id=course.id,
                course_mode=course_mode,
                active_probe_id=payload.active_probe_id,
                reason="standard_course_has_no_concept_graph",
            )

        conversation_id = await self._resolve_owned_thread_id(
            user_id=user_id,
            thread_id=payload.thread_id,
            course_id=course.id,
        )
        active_probe_query = select(AssistantActiveProbe).where(
            AssistantActiveProbe.user_id == user_id,
            AssistantActiveProbe.conversation_id == conversation_id,
            AssistantActiveProbe.course_id == course.id,
        )
        if payload.active_probe_id is not None:
            active_probe_query = active_probe_query.where(AssistantActiveProbe.id == payload.active_probe_id)
        elif payload.lesson_id is not None:
            active_probe_query = active_probe_query.where(
                AssistantActiveProbe.lesson_id == payload.lesson_id,
                AssistantActiveProbe.status == "active",
            )
        else:
            return SubmitConceptProbeResultCapabilityOutput(
                course_id=course.id,
                course_mode=course_mode,
                active_probe_id=None,
                reason="active_probe_not_found",
            )
        if payload.lesson_id is not None:
            active_probe_query = active_probe_query.where(AssistantActiveProbe.lesson_id == payload.lesson_id)
        active_probe = await self._session.scalar(
            active_probe_query.order_by(AssistantActiveProbe.created_at.desc()).limit(1).with_for_update()
        )
        if active_probe is None:
            return SubmitConceptProbeResultCapabilityOutput(
                course_id=course.id,
                course_mode=course_mode,
                active_probe_id=payload.active_probe_id,
                reason="active_probe_not_found",
            )
        if active_probe.status != "active":
            return SubmitConceptProbeResultCapabilityOutput(
                course_id=course.id,
                course_mode=course_mode,
                active_probe_id=active_probe.id,
                concept_id=active_probe.concept_id,
                lesson_id=active_probe.lesson_id,
                reason="active_probe_already_submitted",
            )
        grade = await GradingService(self._session).grade(
            GradeRequest(
                kind="practice_answer",
                question=active_probe.question,
                expected=GradeExpectedPayload(
                    expected_answer=active_probe.expected_answer,
                    answer_kind=cast("PracticeAnswerKind", active_probe.answer_kind),
                    criteria=(
                        "Grade the learner answer for the active chat practice probe. "
                        "Do not reveal the expected answer or full solution in feedback."
                    ),
                ),
                answer=GradeAnswerPayload(answer_text=payload.learner_answer),
                context=GradeContextPayload(
                    course_id=course.id,
                    lesson_id=active_probe.lesson_id,
                    concept_id=active_probe.concept_id,
                    practice_context="quick_check",
                ),
            ),
            user_id,
        )
        rating = 4 if grade.is_correct else 1
        state_service = ConceptStateService(self._session)
        scheduler_service = LectorSchedulerService(self._session)
        updated_state = await state_service.update_mastery(
            user_id=user_id,
            concept_id=active_probe.concept_id,
            correct=grade.is_correct,
        )
        await state_service.log_probe_event(
            user_id=user_id,
            concept_id=active_probe.concept_id,
            rating=rating,
            review_duration_ms=0,
            correct=grade.is_correct,
            context_tag="chat_probe",
            extra={
                "active_probe_id": str(active_probe.id),
                "question": active_probe.question,
                "structure_signature": active_probe.structure_signature,
                "predicted_p_correct": active_probe.predicted_p_correct,
                "target_probability": active_probe.target_probability,
                "target_low": active_probe.target_low,
                "target_high": active_probe.target_high,
                "core_model": active_probe.core_model,
                "answer_kind": active_probe.answer_kind,
            },
        )
        next_review = await scheduler_service.calculate_next_review(
            user_id=user_id,
            course_id=course.id,
            concept_id=active_probe.concept_id,
            rating=rating,
            duration_ms=0,
        )
        await scheduler_service.update_learner_profile(
            user_id=user_id,
            concept_id=active_probe.concept_id,
            rating=rating,
            duration_ms=0,
        )

        active_probe.status = "answered"
        active_probe.answered_correct = grade.is_correct
        active_probe.answer_attempts += 1
        await self._session.flush()

        return SubmitConceptProbeResultCapabilityOutput(
            course_id=course.id,
            course_mode=course_mode,
            active_probe_id=active_probe.id,
            concept_id=active_probe.concept_id,
            lesson_id=active_probe.lesson_id,
            is_correct=grade.is_correct,
            status=grade.status,
            feedback_markdown=_build_safe_chat_probe_feedback(is_correct=grade.is_correct),
            mastery=updated_state.s_mastery,
            exposures=updated_state.exposures,
            next_review_at=next_review,
            tags=[],
        )

    async def _resolve_owned_thread_id(
        self,
        *,
        user_id: uuid.UUID,
        thread_id: uuid.UUID | None,
        course_id: uuid.UUID,
    ) -> uuid.UUID | None:
        if thread_id is None:
            detail = "Assistant thread is required for chat probe generation."
            raise LearningCapabilitiesValidationError(detail)

        owned_thread_id = await self._session.scalar(
            select(AssistantConversation.id).where(
                AssistantConversation.id == thread_id,
                AssistantConversation.user_id == user_id,
                AssistantConversation.context_type == "course",
                AssistantConversation.context_id == course_id,
            )
        )
        if owned_thread_id is None:
            detail = "Assistant thread not found or access denied."
            raise LearningCapabilitiesValidationError(detail)
        return owned_thread_id

    async def _get_active_probe(
        self,
        *,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID | None,
        course_id: uuid.UUID,
        concept_id: uuid.UUID,
    ) -> AssistantActiveProbe | None:
        if conversation_id is None:
            return None
        return await self._session.scalar(
            select(AssistantActiveProbe)
            .where(
                AssistantActiveProbe.user_id == user_id,
                AssistantActiveProbe.conversation_id == conversation_id,
                AssistantActiveProbe.course_id == course_id,
                AssistantActiveProbe.concept_id == concept_id,
                AssistantActiveProbe.status == "active",
            )
            .order_by(AssistantActiveProbe.created_at.desc())
            .limit(1)
        )

    async def _get_active_probe_for_lesson(
        self,
        *,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID | None,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
        concept_id: uuid.UUID,
    ) -> AssistantActiveProbe | None:
        if conversation_id is None:
            return None
        return await self._session.scalar(
            select(AssistantActiveProbe)
            .where(
                AssistantActiveProbe.user_id == user_id,
                AssistantActiveProbe.conversation_id == conversation_id,
                AssistantActiveProbe.course_id == course_id,
                AssistantActiveProbe.lesson_id == lesson_id,
                AssistantActiveProbe.concept_id == concept_id,
                AssistantActiveProbe.status == "active",
            )
            .order_by(AssistantActiveProbe.created_at.desc())
            .limit(1)
        )

    async def _lesson_matches_concept(
        self,
        *,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
        concept_id: uuid.UUID,
    ) -> bool:
        lesson_exists = await self._session.scalar(
            select(Lesson.id).where(
                Lesson.id == lesson_id,
                Lesson.course_id == course_id,
                Lesson.concept_id == concept_id,
            )
        )
        return lesson_exists is not None

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
        base_context = await lesson_service._prepare_lesson_context(  # noqa: SLF001
            lesson=lesson,
            course=course,
            generation_mode="learning_capability_mutation",
        )
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
        generated = await llm_client.generate_lesson_content(
            composed_context,
            user_id=user_id,
            function_tools=[build_wikipedia_resolver_function_tool()],
        )
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


def _probe_lookup_reason(error: LookupError) -> str:
    message = str(error).lower()
    if "lesson" in message:
        return "lesson_not_assigned_to_concept"
    return "concept_not_assigned_to_course"


def _active_probe_output(
    *,
    course: Course,
    course_mode: CourseMode,
    active_probe: AssistantActiveProbe,
) -> GenerateConceptProbeCapabilityOutput:
    probe = ChatConceptProbe(
        active_probe_id=active_probe.id,
        question=active_probe.question,
        answer_kind=active_probe.answer_kind,
        hints=list(active_probe.hints),
        course_id=course.id,
        concept_id=active_probe.concept_id,
        lesson_id=active_probe.lesson_id,
    )
    return GenerateConceptProbeCapabilityOutput(
        course_id=course.id,
        course_mode=course_mode,
        concept_id=active_probe.concept_id,
        active_probe_id=active_probe.id,
        probe=probe,
    )


def _build_safe_chat_probe_feedback(*, is_correct: bool) -> str:
    if is_correct:
        return "Your answer was graded correct. The detailed answer is kept hidden so you can keep practicing."
    return "Your answer needs revision. The detailed answer is kept hidden so you can try again."


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
