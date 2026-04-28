import uuid

from sqlalchemy.ext.asyncio import AsyncSession


"""
Courses Module Facade.

Single entry point for all course-related operations.
Coordinates internal course services and provides stable API for other modules.
"""

import logging
from datetime import UTC, datetime
from typing import Any, cast

from fastapi import BackgroundTasks, status
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from src.ai.errors import AIRuntimeError
from src.exceptions import (
    BadRequestError,
    ConflictError,
    DomainError,
    ErrorCategory,
    ErrorCode,
    NotFoundError,
    UpstreamUnavailableError,
    ValidationError,
)

from .models import Course, CourseConcept, LearningAttempt, LearningQuestion, Lesson
from .schemas import (
    AttemptRequest,
    AttemptResponse,
    ConceptReviewRequest,
    CourseResponse,
    FrontierResponse,
    GradeAnswerPayload,
    GradeContextPayload,
    GradeExpectedPayload,
    GradeRequest,
    GradeResponse,
    LessonDetailResponse,
    LessonVersionHistoryResponse,
    NextReviewResponse,
    QuestionSetItem,
    QuestionSetRequest,
    QuestionSetResponse,
    ReviewBatchRequest,
    ReviewBatchResponse,
    ReviewOutcome,
    ReviewRequest,
)
from .services.concept_graph_service import ConceptGraphService
from .services.concept_scheduler_service import LectorSchedulerService
from .services.concept_state_service import ConceptStateService
from .services.course_content_service import CourseContentService
from .services.course_progress_service import CourseProgressService
from .services.course_query_service import CourseQueryService
from .services.frontier_builder import build_course_frontier
from .services.grading_service import GradingService
from .services.lesson_service import LessonService
from .services.practice_drill_service import PracticeDrillService


logger = logging.getLogger(__name__)


FEATURE_AREA = "courses"


class CoursesFacadeNotFoundError(NotFoundError):
    """Raised when a requested course resource is not available to the caller."""

    def __init__(self, detail: str = "Course not found") -> None:
        super().__init__(message=detail, feature_area=FEATURE_AREA)


class CoursesFacadeBadRequestError(BadRequestError):
    """Raised when a course operation is invalid for the current domain state."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail, feature_area=FEATURE_AREA)


class CoursesFacadeValidationError(ValidationError):
    """Raised when course payloads fail domain validation."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail, feature_area=FEATURE_AREA)


class CoursesFacadeConflictError(ConflictError):
    """Raised when an idempotency key is reused for a different payload."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail, feature_area=FEATURE_AREA)


class CoursesFacadeUpstreamError(UpstreamUnavailableError):
    """Raised when course workflows fail on upstream or internal dependencies."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail, feature_area=FEATURE_AREA)


class CoursesFacadeInternalError(DomainError):
    """Raised when course workflows fail with internal processing errors."""

    category = ErrorCategory.INTERNAL
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_error_code = ErrorCode.INTERNAL

    def __init__(self, detail: str) -> None:
        super().__init__(detail, feature_area=FEATURE_AREA)


class CoursesFacade:  # noqa: PLR0904
    """
    Single entry point for all course operations.

    Coordinates internal course services, publishes events, and provides
    stable API that won't break when internal implementation changes.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._content_service = CourseContentService(session)
        self._progress_service = CourseProgressService(session)

    async def get_content_with_progress(self, content_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, Any]:
        """Get course content with progress for cross-module progress contracts."""
        course_response = await self.get_course(content_id, user_id)
        progress = await self._progress_service.get_progress(content_id, user_id)
        return {
            "course": course_response.model_dump(),
            "progress": progress,
            "completion_percentage": progress.get("completion_percentage", 0),
            "current_lesson": progress.get("current_lesson", ""),
            "total_lessons": progress.get("total_lessons", 0),
            "completed_lessons": progress.get("completed_lessons", {}),
        }

    async def get_course(
        self,
        course_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> CourseResponse:
        """Get a course for the authenticated user."""
        query_service = CourseQueryService(self._session)
        try:
            return await query_service.get_course(course_id, user_id)
        except NotFoundError:
            raise
        except (SQLAlchemyError, RuntimeError, ValueError, TypeError) as error:
            logger.exception("Error getting course %s for user %s", course_id, user_id)
            message = "Failed to retrieve course"
            raise CoursesFacadeUpstreamError(message) from error

    async def create_course(
        self,
        course_data: dict[str, Any],
        user_id: uuid.UUID,
        background_tasks: BackgroundTasks | None = None,
        attachments: list[Any] | None = None,
    ) -> CourseResponse:
        """Create a new course entry and return its canonical response model."""
        try:
            created_course = await self._content_service.create_course(
                course_data,
                user_id,
                background_tasks=background_tasks,
                attachments=attachments,
            )
            query_service = CourseQueryService(self._session)
            return await query_service.get_course(created_course.id, user_id)
        except NotFoundError:
            raise
        except (SQLAlchemyError, RuntimeError, ValueError, TypeError) as error:
            logger.exception("Error creating course for user %s", user_id)
            message = "Failed to create course"
            raise CoursesFacadeUpstreamError(message) from error

    # NOTE: Auto-tagging removed - now handled by CourseContentService via BaseContentService pipeline
    # Tagging happens automatically during course creation/updates, no manual intervention needed

    async def generate_ai_course(
        self,
        topic: str,
        preferences: dict[str, Any],
        user_id: uuid.UUID,
        background_tasks: BackgroundTasks | None = None,
    ) -> CourseResponse:
        """Generate an AI-powered course and return the created course response."""
        data: dict[str, Any] = {**(preferences or {})}
        data["prompt"] = topic
        try:
            course = await self._content_service.create_course(
                data,
                user_id,
                background_tasks=background_tasks,
            )
            query_service = CourseQueryService(self._session)
            return await query_service.get_course(course.id, user_id)
        except NotFoundError:
            raise
        except (SQLAlchemyError, RuntimeError, ValueError, TypeError) as error:
            logger.exception("courses.generate_ai.failed", extra={"topic": topic, "user_id": str(user_id)})
            message = "Failed to generate course"
            raise CoursesFacadeUpstreamError(message) from error

    async def update_progress(
        self, content_id: uuid.UUID, user_id: uuid.UUID, progress_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Update course progress.

        Implements ContentFacade interface.
        """
        return await self.update_course_progress(content_id, user_id, progress_data)

    async def update_course_progress(
        self, course_id: uuid.UUID, user_id: uuid.UUID, progress_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update course progress and return the updated progress payload."""
        try:
            updated_progress = await self._progress_service.update_progress(course_id, user_id, progress_data)
        except (SQLAlchemyError, RuntimeError, ValueError, TypeError) as error:
            logger.exception("courses.progress.update_failed", extra={"course_id": str(course_id)})
            message = "Failed to update course progress"
            raise CoursesFacadeUpstreamError(message) from error

        return {"progress": updated_progress}

    async def update_course(
        self, course_id: uuid.UUID, user_id: uuid.UUID, update_data: dict[str, Any]
    ) -> CourseResponse:
        """Update course metadata and return the updated course response."""
        try:
            updated_course = await self._content_service.update_course(course_id, update_data, user_id)
            query_service = CourseQueryService(self._session)
            return await query_service.get_course(updated_course.id, user_id)
        except NotFoundError:
            raise
        except (SQLAlchemyError, RuntimeError, ValueError, TypeError) as error:
            logger.exception("Error updating course %s", course_id)
            message = "Failed to update course"
            raise CoursesFacadeUpstreamError(message) from error

    async def list_courses(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        per_page: int = 20,
        search: str | None = None,
    ) -> tuple[list[CourseResponse], int]:
        """List user courses with pagination and optional search."""
        query_service = CourseQueryService(self._session)
        try:
            return await query_service.list_courses(
                page=page,
                per_page=per_page,
                search=search,
                user_id=user_id,
            )
        except (SQLAlchemyError, RuntimeError, ValueError, TypeError) as error:
            logger.exception("Error listing courses for user %s", user_id)
            message = "Failed to list courses"
            raise CoursesFacadeUpstreamError(message) from error

    async def search_courses(
        self, query: str, user_id: uuid.UUID, filters: dict[str, Any] | None = None
    ) -> list[CourseResponse]:
        """Search user courses and return the matching course responses."""
        query_service = CourseQueryService(self._session)
        limit = (filters or {}).get("limit", 20)
        try:
            results, _total = await query_service.list_courses(per_page=limit, search=query, user_id=user_id)
            return results
        except (SQLAlchemyError, RuntimeError, ValueError, TypeError) as error:
            logger.exception("Error searching courses for user %s", user_id)
            message = "Search failed"
            raise CoursesFacadeUpstreamError(message) from error

    async def get_user_courses(self, user_id: uuid.UUID, include_progress: bool = True) -> list[dict[str, Any]]:
        """Get all courses for user, optionally including progress information."""
        query_service = CourseQueryService(self._session)
        per_page = 20
        try:
            course_responses, _total = await query_service.list_courses(
                page=1, per_page=per_page, search=None, user_id=user_id
            )
        except (SQLAlchemyError, RuntimeError, ValueError, TypeError) as error:
            logger.exception("courses.list_user.failed", extra={"user_id": str(user_id)})
            message = "Failed to get courses"
            raise CoursesFacadeUpstreamError(message) from error

        course_dicts: list[dict[str, Any]] = []
        for course_response in course_responses:
            course_dict = course_response.model_dump()
            if include_progress:
                try:
                    progress = await self._progress_service.get_progress(course_response.id, user_id)
                    course_dict["progress"] = progress
                except (RuntimeError, ValueError) as error:
                    logger.warning("Failed to get progress for course %s: %s", course_response.id, error)
                    course_dict["progress"] = {"completion_percentage": 0, "completed_lessons": {}}
            course_dicts.append(course_dict)

        return course_dicts

    async def get_course_lessons(self, course_id: uuid.UUID, user_id: uuid.UUID) -> list[dict[str, Any]]:
        """Get course lessons grouped by modules."""
        query_service = CourseQueryService(self._session)
        try:
            course_response = await query_service.get_course(course_id, user_id)
            progress = await self._progress_service.get_progress(course_id, user_id)
        except NotFoundError:
            raise
        except (SQLAlchemyError, RuntimeError, ValueError, TypeError) as error:
            logger.exception("Error getting lessons for course %s", course_id)
            message = "Failed to get lessons"
            raise CoursesFacadeUpstreamError(message) from error

        completed_lessons = progress.get("completed_lessons", {}) if isinstance(progress, dict) else {}
        lessons_payload: list[dict[str, Any]] = []
        for module in course_response.modules:
            for lesson in module.lessons:
                lesson_dict = lesson.model_dump()
                lesson_dict["moduleTitle"] = module.title
                lesson_dict["moduleId"] = str(module.id)
                lesson_dict["completed"] = completed_lessons.get(str(lesson.id), False)
                lessons_payload.append(lesson_dict)

        return lessons_payload

    async def _require_owned_course(self, *, course_id: uuid.UUID, user_id: uuid.UUID) -> Course:
        course = await self._session.scalar(
            select(Course).where(
                Course.id == course_id,
                Course.user_id == user_id,
            )
        )
        if course is None:
            detail = "Course not found"
            raise CoursesFacadeNotFoundError(detail)
        return course

    async def get_lesson(
        self,
        *,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
        user_id: uuid.UUID,
        generate: bool = False,
        version_id: uuid.UUID | None = None,
    ) -> LessonDetailResponse:
        """Get a lesson detail payload for an owned course."""
        lesson_service = LessonService(self._session, user_id)
        return await lesson_service.get_lesson(
            course_id,
            lesson_id,
            force_refresh=generate,
            version_id=version_id,
        )

    async def list_lesson_versions(
        self,
        *,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> LessonVersionHistoryResponse:
        """Return version history for an owned lesson."""
        lesson_service = LessonService(self._session, user_id)
        return await lesson_service.list_lesson_versions(course_id=course_id, lesson_id=lesson_id)

    async def regenerate_lesson(
        self,
        *,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
        critique_text: str,
        apply_across_course: bool,
        user_id: uuid.UUID,
    ) -> LessonDetailResponse:
        """Regenerate a lesson body with explicit learner feedback."""
        lesson_service = LessonService(self._session, user_id)

        try:
            return await lesson_service.regenerate_lesson(
                course_id=course_id,
                lesson_id=lesson_id,
                critique_text=critique_text,
                apply_across_course=apply_across_course,
            )
        except NotFoundError, UpstreamUnavailableError, ValidationError:
            raise
        except (SQLAlchemyError, RuntimeError, TypeError, ValueError) as error:
            logger.exception(
                "courses.lesson.regenerate.failed",
                extra={"course_id": str(course_id), "lesson_id": str(lesson_id), "user_id": str(user_id)},
            )
            message = "Failed to regenerate lesson"
            raise CoursesFacadeUpstreamError(message) from error

    async def start_next_lesson_pass(
        self,
        *,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
        force: bool,
        user_id: uuid.UUID,
    ) -> LessonDetailResponse:
        """Create or select the next major pass for one adaptive lesson."""
        lesson_service = LessonService(self._session, user_id)

        try:
            return await lesson_service.start_next_pass(
                course_id=course_id,
                lesson_id=lesson_id,
                force=force,
            )
        except DomainError:
            raise
        except (SQLAlchemyError, RuntimeError, TypeError, ValueError) as error:
            logger.exception(
                "courses.lesson.next_pass.failed",
                extra={"course_id": str(course_id), "lesson_id": str(lesson_id), "user_id": str(user_id)},
            )
            message = "Failed to start the next lesson pass"
            raise CoursesFacadeUpstreamError(message) from error

    async def grade_lesson_response(
        self,
        *,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
        payload: GradeRequest,
        user_id: uuid.UUID,
    ) -> GradeResponse:
        """Grade a learner response with course, lesson, and concept validation."""
        await self._require_owned_course(course_id=course_id, user_id=user_id)

        if payload.context.course_id != course_id:
            detail = "Context courseId does not match the request path"
            raise CoursesFacadeValidationError(detail)
        if payload.context.lesson_id != lesson_id:
            detail = "Context lessonId does not match the request path"
            raise CoursesFacadeValidationError(detail)

        lesson_row = (
            await self._session.execute(
                select(Lesson.id, Lesson.concept_id).where(
                    Lesson.id == lesson_id,
                    Lesson.course_id == course_id,
                )
            )
        ).first()
        if lesson_row is None:
            detail = "Lesson not found"
            raise CoursesFacadeNotFoundError(detail)

        _lesson_row_id, lesson_concept_id = lesson_row
        if lesson_concept_id is not None:
            if lesson_concept_id != payload.context.concept_id:
                detail = "Context conceptId does not match the request lesson"
                raise CoursesFacadeValidationError(detail)
        else:
            concept_link = await self._session.scalar(
                select(CourseConcept.concept_id).where(
                    CourseConcept.course_id == course_id,
                    CourseConcept.concept_id == payload.context.concept_id,
                )
            )
            if concept_link is None:
                detail = "Concept is not assigned to this course"
                raise CoursesFacadeNotFoundError(detail)

        grading_service = GradingService(self._session)
        try:
            return await grading_service.grade(payload, user_id)
        except (AIRuntimeError, TypeError, ValueError) as error:
            logger.exception(
                "courses.grade.upstream_failed",
                extra={"course_id": str(course_id), "lesson_id": str(lesson_id), "user_id": str(user_id)},
            )
            message = "Grading service is temporarily unavailable"
            raise CoursesFacadeUpstreamError(message) from error
        except RuntimeError as error:
            logger.exception(
                "courses.grade.failed",
                extra={"course_id": str(course_id), "lesson_id": str(lesson_id), "user_id": str(user_id)},
            )
            message = "Failed to grade response"
            raise CoursesFacadeInternalError(message) from error

    async def get_course_concept_frontier(
        self,
        *,
        course_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> FrontierResponse:
        """Return adaptive frontier data for a course."""
        course = await self._require_owned_course(course_id=course_id, user_id=user_id)
        if not course.adaptive_enabled:
            return FrontierResponse(
                frontier=[],
                due_for_review=[],
                coming_soon=[],
                due_count=0,
                avg_mastery=0.0,
            )

        graph_service = ConceptGraphService(self._session)
        scheduler_service = LectorSchedulerService(self._session)
        return await build_course_frontier(
            session=self._session,
            user_id=user_id,
            course_id=course_id,
            graph_service=graph_service,
            scheduler_service=scheduler_service,
        )

    async def create_question_set(
        self,
        *,
        course_id: uuid.UUID,
        payload: QuestionSetRequest,
        user_id: uuid.UUID,
    ) -> QuestionSetResponse:
        """Generate and store server-owned questions for later attempts."""
        course = await self._require_owned_course(course_id=course_id, user_id=user_id)
        if not course.adaptive_enabled:
            detail = "Adaptive scheduling is not enabled for this course"
            raise CoursesFacadeBadRequestError(detail)

        drill_service = PracticeDrillService(self._session)
        try:
            drills = await drill_service.generate_drills(
                user_id=user_id,
                course_id=course.id,
                concept_id=payload.concept_id,
                count=payload.count,
            )
        except LookupError as error:
            raise CoursesFacadeNotFoundError(str(error)) from error
        except ValueError as error:
            raise CoursesFacadeValidationError(str(error)) from error
        except (RuntimeError, TypeError) as error:
            logger.exception(
                "QUESTION_SET_GENERATION_FAILED",
                extra={
                    "course_id": str(course.id),
                    "user_id": str(user_id),
                    "concept_id": str(payload.concept_id),
                    "count": payload.count,
                },
            )
            detail = "Failed to generate question set"
            raise CoursesFacadeUpstreamError(detail) from error

        questions: list[QuestionSetItem] = []
        for drill in drills:
            if payload.lesson_id is not None and payload.lesson_id != drill.lesson_id:
                detail = "lessonId does not match the generated concept lesson"
                raise CoursesFacadeValidationError(detail)
            stored = LearningQuestion(
                user_id=user_id,
                course_id=course.id,
                concept_id=payload.concept_id,
                lesson_id=drill.lesson_id,
                question=drill.question,
                expected_answer=drill.expected_answer,
                answer_kind=drill.answer_kind,
                hints=drill.hints,
                structure_signature=drill.structure_signature,
                predicted_p_correct=drill.predicted_p_correct,
                target_probability=drill.target_probability,
                target_low=drill.target_low,
                target_high=drill.target_high,
                core_model=drill.core_model,
                practice_context=payload.practice_context,
            )
            self._session.add(stored)
            await self._session.flush()
            questions.append(
                QuestionSetItem(
                    question_id=stored.id,
                    concept_id=stored.concept_id,
                    lesson_id=stored.lesson_id,
                    question=stored.question,
                    input_kind=cast("Any", stored.answer_kind),
                    hints=stored.hints,
                )
            )

        return QuestionSetResponse(questions=questions)

    async def submit_attempt(
        self,
        *,
        course_id: uuid.UUID,
        payload: AttemptRequest,
        user_id: uuid.UUID,
    ) -> AttemptResponse:
        """Grade one server-owned question and apply learning side effects once."""
        await self._require_owned_course(course_id=course_id, user_id=user_id)

        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:attempt_id, 0))"),
            {"attempt_id": str(payload.attempt_id)},
        )

        existing_attempt = await self._session.scalar(
            select(LearningAttempt).where(
                LearningAttempt.user_id == user_id,
                LearningAttempt.attempt_id == payload.attempt_id,
            )
        )
        if existing_attempt is not None:
            return self._response_for_existing_attempt(
                existing_attempt,
                course_id=course_id,
                payload=payload,
            )

        question = await self._session.scalar(
            select(LearningQuestion).where(
                LearningQuestion.id == payload.question_id,
                LearningQuestion.user_id == user_id,
                LearningQuestion.course_id == course_id,
            ).with_for_update()
        )
        if question is None:
            detail = "Question not found"
            raise CoursesFacadeNotFoundError(detail)

        existing_attempt = await self._session.scalar(
            select(LearningAttempt).where(
                LearningAttempt.user_id == user_id,
                LearningAttempt.attempt_id == payload.attempt_id,
            )
        )
        if existing_attempt is not None:
            return self._response_for_existing_attempt(
                existing_attempt,
                course_id=course_id,
                payload=payload,
            )

        if question.status != "active":
            detail = "Question has already been answered"
            raise CoursesFacadeBadRequestError(detail)
        if question.lesson_id is None:
            detail = "Question is missing lesson context"
            raise CoursesFacadeValidationError(detail)
        lesson_id = question.lesson_id

        return await self._grade_and_record_attempt(
            course_id=course_id,
            question=question,
            lesson_id=lesson_id,
            payload=payload,
            user_id=user_id,
        )

    def _response_for_existing_attempt(
        self,
        attempt: LearningAttempt,
        *,
        course_id: uuid.UUID,
        payload: AttemptRequest,
    ) -> AttemptResponse:
        if (
            attempt.course_id != course_id
            or attempt.question_id != payload.question_id
            or attempt.learner_answer != payload.learner_answer
            or attempt.hints_used != payload.hints_used
            or attempt.duration_ms != payload.duration_ms
        ):
            detail = "attemptId was already used for a different answer"
            raise CoursesFacadeConflictError(detail)
        return AttemptResponse.model_validate(attempt.response_payload)

    async def _grade_and_record_attempt(
        self,
        *,
        course_id: uuid.UUID,
        question: LearningQuestion,
        lesson_id: uuid.UUID,
        payload: AttemptRequest,
        user_id: uuid.UUID,
    ) -> AttemptResponse:
        rating = 1
        learner_answer = payload.learner_answer.strip()
        if learner_answer.lower() == "skip":
            is_correct = False
            attempt_status = "unsupported"
            feedback = "Skipped for now. This is recorded so the next review can focus on this concept."
        else:
            grade = await self._grade_attempt_answer(
                course_id=course_id,
                question=question,
                lesson_id=lesson_id,
                payload=payload,
                learner_answer=learner_answer,
                user_id=user_id,
            )
            is_correct = grade.is_correct
            attempt_status = "unsupported" if grade.status == "unsupported" else ("correct" if grade.is_correct else "incorrect")
            feedback = grade.feedback_markdown
            rating = 4 if grade.is_correct else 1

        state_service = ConceptStateService(self._session)
        scheduler_service = LectorSchedulerService(self._session)
        updated_state = await state_service.update_mastery(
            user_id=user_id,
            concept_id=question.concept_id,
            correct=is_correct,
            latency_ms=payload.duration_ms,
        )
        await state_service.log_probe_event(
            user_id=user_id,
            concept_id=question.concept_id,
            rating=rating,
            review_duration_ms=payload.duration_ms,
            correct=is_correct,
            latency_ms=payload.duration_ms,
            context_tag=f"{question.practice_context}:{lesson_id}",
            extra={
                "question_id": str(question.id),
                "question": question.question,
                "structure_signature": question.structure_signature,
                "predicted_p_correct": float(question.predicted_p_correct),
                "target_probability": float(question.target_probability),
                "target_low": float(question.target_low),
                "target_high": float(question.target_high),
                "core_model": question.core_model,
                "attempt_id": str(payload.attempt_id),
                "status": attempt_status,
            },
        )
        next_review = await scheduler_service.calculate_next_review(
            user_id=user_id,
            course_id=course_id,
            concept_id=question.concept_id,
            rating=rating,
            duration_ms=payload.duration_ms,
        )
        await scheduler_service.update_learner_profile(
            user_id=user_id,
            concept_id=question.concept_id,
            rating=rating,
            duration_ms=payload.duration_ms,
        )

        question.status = "answered"
        question.updated_at = datetime.now(UTC)
        response = AttemptResponse(
            attempt_id=payload.attempt_id,
            is_correct=is_correct,
            status=cast("Any", attempt_status),
            feedback_markdown=feedback,
            mastery=updated_state.s_mastery,
            exposures=updated_state.exposures,
            next_review_at=next_review,
        )
        attempt = LearningAttempt(
            attempt_id=payload.attempt_id,
            user_id=user_id,
            course_id=course_id,
            question_id=question.id,
            learner_answer=payload.learner_answer,
            hints_used=payload.hints_used,
            duration_ms=payload.duration_ms,
            is_correct=response.is_correct,
            grade_status=response.status,
            feedback_markdown=response.feedback_markdown,
            mastery=response.mastery,
            exposures=response.exposures,
            next_review_at=response.next_review_at,
            response_payload=response.model_dump(mode="json"),
        )
        self._session.add(attempt)
        await self._session.flush()

        concept_stats: dict[str, dict[str, Any]] = {}
        snapshot = {
            "concept_id": str(question.concept_id),
            "rating": rating,
            "duration_ms": payload.duration_ms,
            "next_review_at": next_review.isoformat() if next_review else None,
            "mastery": float(updated_state.s_mastery or 0.0),
            "exposures": int(updated_state.exposures),
            "reviewed_at": datetime.now(UTC).isoformat(),
        }
        self._update_review_stats(concept_stats=concept_stats, review_snapshot=snapshot)
        progress_service = CourseProgressService(self._session)
        await progress_service.update_progress(
            course_id,
            user_id,
            self._build_review_progress_payload(
                lesson_id=lesson_id,
                last_review_snapshot=snapshot,
                concept_stats=concept_stats,
            ),
        )
        return response

    async def _grade_attempt_answer(
        self,
        *,
        course_id: uuid.UUID,
        question: LearningQuestion,
        lesson_id: uuid.UUID,
        payload: AttemptRequest,
        learner_answer: str,
        user_id: uuid.UUID,
    ) -> GradeResponse:
        try:
            return await GradingService(self._session).grade(
                GradeRequest(
                    kind="practice_answer",
                    question=question.question,
                    expected=GradeExpectedPayload(
                        expected_answer=question.expected_answer,
                        answer_kind=cast("Any", question.answer_kind),
                    ),
                    answer=GradeAnswerPayload(answer_text=learner_answer),
                    context=GradeContextPayload(
                        course_id=course_id,
                        lesson_id=lesson_id,
                        concept_id=question.concept_id,
                        practice_context=cast("Any", question.practice_context),
                        hints_used=payload.hints_used,
                    ),
                ),
                user_id,
            )
        except (RuntimeError, TypeError, ValueError) as error:
            logger.exception(
                "courses.attempt.grading_failed",
                extra={
                    "course_id": str(course_id),
                    "question_id": str(question.id),
                    "user_id": str(user_id),
                },
            )
            detail = "Grading service is temporarily unavailable"
            raise CoursesFacadeUpstreamError(detail) from error

    async def submit_adaptive_reviews(
        self,
        *,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
        payload: ReviewBatchRequest,
        user_id: uuid.UUID,
    ) -> ReviewBatchResponse:
        """Submit concept reviews for LECTOR scheduling."""
        course = await self._require_owned_course(course_id=course_id, user_id=user_id)
        if not course.adaptive_enabled:
            detail = "Adaptive scheduling is not enabled for this course"
            raise CoursesFacadeBadRequestError(detail)

        await self._assert_course_contains_review_concepts(course_id=course.id, reviews=payload.reviews)

        state_service = ConceptStateService(self._session)
        scheduler_service = LectorSchedulerService(self._session)

        outcomes: list[ReviewOutcome] = []
        concept_stats: dict[str, dict[str, Any]] = {}
        last_review_snapshot: dict[str, Any] | None = None

        for review in payload.reviews:
            review_outcome, review_snapshot = await self._process_adaptive_review(
                course_id=course.id,
                lesson_id=lesson_id,
                user_id=user_id,
                review=review,
                state_service=state_service,
                scheduler_service=scheduler_service,
            )
            outcomes.append(review_outcome)
            self._update_review_stats(concept_stats=concept_stats, review_snapshot=review_snapshot)
            last_review_snapshot = review_snapshot

        await self._session.flush()

        if last_review_snapshot is not None:
            try:
                progress_service = CourseProgressService(self._session)
                await progress_service.update_progress(
                    course.id,
                    user_id,
                    self._build_review_progress_payload(
                        lesson_id=lesson_id,
                        last_review_snapshot=last_review_snapshot,
                        concept_stats=concept_stats,
                    ),
                )
            except SQLAlchemyError:
                logger.exception(
                    "COURSE_PROGRESS_UPDATE_FAILED",
                    extra={
                        "course_id": str(course.id),
                        "user_id": str(user_id),
                        "lesson_id": str(lesson_id),
                    },
                )

        return ReviewBatchResponse(outcomes=outcomes)

    async def submit_concept_review(
        self,
        *,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
        payload: ConceptReviewRequest,
        user_id: uuid.UUID,
    ) -> ReviewBatchResponse:
        """Submit one explicit learner self-rating for a concept."""
        await self._require_owned_course(course_id=course_id, user_id=user_id)
        lesson_exists = await self._session.scalar(
            select(Lesson.id).where(
                Lesson.id == lesson_id,
                Lesson.course_id == course_id,
            )
        )
        if lesson_exists is None:
            detail = "Lesson not found"
            raise CoursesFacadeNotFoundError(detail)

        review = ReviewRequest(
            concept_id=payload.concept_id,
            rating=payload.rating,
            review_duration_ms=payload.review_duration_ms,
        )
        return await self.submit_adaptive_reviews(
            course_id=course_id,
            lesson_id=lesson_id,
            payload=ReviewBatchRequest(reviews=[review]),
            user_id=user_id,
        )

    async def _assert_course_contains_review_concepts(self, *, course_id: uuid.UUID, reviews: list[Any]) -> None:
        concept_ids = {review.concept_id for review in reviews}
        existing = await self._session.execute(
            select(CourseConcept.concept_id).where(
                CourseConcept.course_id == course_id,
                CourseConcept.concept_id.in_(concept_ids),
            )
        )
        found_ids = set(existing.scalars().all())
        if concept_ids - found_ids:
            detail = "One or more concepts are not assigned to this course"
            raise CoursesFacadeNotFoundError(detail)

    def _build_review_extra(self, *, review: Any) -> dict[str, Any]:
        review_extra: dict[str, Any] = {"rating": review.rating}
        if review.question:
            review_extra["question"] = review.question
        if review.structure_signature:
            review_extra["structure_signature"] = review.structure_signature
        if review.predicted_p_correct is not None:
            review_extra["predicted_p_correct"] = float(review.predicted_p_correct)
        if review.target_probability is not None:
            review_extra["target_probability"] = float(review.target_probability)
        if review.target_low is not None:
            review_extra["target_low"] = float(review.target_low)
        if review.target_high is not None:
            review_extra["target_high"] = float(review.target_high)
        if review.core_model:
            review_extra["core_model"] = review.core_model
        return review_extra

    async def _process_adaptive_review(
        self,
        *,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
        user_id: uuid.UUID,
        review: Any,
        state_service: ConceptStateService,
        scheduler_service: LectorSchedulerService,
    ) -> tuple[ReviewOutcome, dict[str, Any]]:
        correct = review.rating >= 3
        updated_state = await state_service.update_mastery(
            user_id=user_id,
            concept_id=review.concept_id,
            correct=correct,
            latency_ms=review.latency_ms,
        )
        await state_service.log_probe_event(
            user_id=user_id,
            concept_id=review.concept_id,
            rating=review.rating,
            review_duration_ms=review.review_duration_ms,
            correct=correct,
            latency_ms=review.latency_ms,
            context_tag=f"lesson:{lesson_id}",
            extra=self._build_review_extra(review=review),
        )
        next_review = await scheduler_service.calculate_next_review(
            user_id=user_id,
            course_id=course_id,
            concept_id=review.concept_id,
            rating=review.rating,
            duration_ms=review.review_duration_ms,
        )
        await scheduler_service.update_learner_profile(
            user_id=user_id,
            concept_id=review.concept_id,
            rating=review.rating,
            duration_ms=review.review_duration_ms,
        )
        return ReviewOutcome(
            concept_id=review.concept_id,
            next_review_at=next_review,
            mastery=updated_state.s_mastery,
            exposures=updated_state.exposures,
        ), {
            "concept_id": str(review.concept_id),
            "rating": review.rating,
            "duration_ms": review.review_duration_ms,
            "next_review_at": next_review.isoformat() if next_review else None,
            "mastery": float(updated_state.s_mastery or 0.0),
            "exposures": int(updated_state.exposures),
            "reviewed_at": datetime.now(UTC).isoformat(),
        }

    def _update_review_stats(
        self,
        *,
        concept_stats: dict[str, dict[str, Any]],
        review_snapshot: dict[str, Any],
    ) -> None:
        concept_key = cast("str", review_snapshot["concept_id"])
        stats = concept_stats.setdefault(
            concept_key,
            {
                "ratingCounts": {"1": 0, "2": 0, "3": 0, "4": 0},
                "totalDurationMs": 0,
            },
        )
        rating_counts = cast("dict[str, int]", stats["ratingCounts"])
        rating_key = str(review_snapshot["rating"])
        rating_counts[rating_key] = rating_counts.get(rating_key, 0) + 1
        stats["totalDurationMs"] = int(stats["totalDurationMs"]) + int(review_snapshot["duration_ms"])
        stats.update(
            {
                "lastRating": review_snapshot["rating"],
                "lastDurationMs": review_snapshot["duration_ms"],
                "lastReviewedAt": review_snapshot["reviewed_at"],
                "lastNextReviewAt": review_snapshot["next_review_at"],
                "mastery": review_snapshot["mastery"],
                "exposures": review_snapshot["exposures"],
            }
        )

    def _build_review_progress_payload(
        self,
        *,
        lesson_id: uuid.UUID,
        last_review_snapshot: dict[str, Any],
        concept_stats: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "current_lesson_id": str(lesson_id),
            "last_reviewed_concept": last_review_snapshot["concept_id"],
            "last_reviewed_rating": last_review_snapshot["rating"],
            "last_review_duration_ms": last_review_snapshot["duration_ms"],
            "last_reviewed_at": datetime.now(UTC).isoformat(),
            "last_next_review_at": last_review_snapshot["next_review_at"],
            "concept_review_stats": concept_stats,
        }

    async def get_concept_next_review(
        self,
        *,
        course_id: uuid.UUID,
        concept_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> NextReviewResponse:
        """Return the next scheduled review information for a concept."""
        course = await self._require_owned_course(course_id=course_id, user_id=user_id)
        if not course.adaptive_enabled:
            detail = "Adaptive scheduling is not enabled for this course"
            raise CoursesFacadeBadRequestError(detail)

        linkage = await self._session.execute(
            select(CourseConcept.concept_id).where(
                CourseConcept.course_id == course.id,
                CourseConcept.concept_id == concept_id,
            )
        )
        if linkage.scalar_one_or_none() is None:
            detail = "Concept is not assigned to this course"
            raise CoursesFacadeNotFoundError(detail)

        state_service = ConceptStateService(self._session)
        state = await state_service.get_user_concept_state(
            user_id=user_id,
            concept_id=concept_id,
            create=False,
        )
        if state is None:
            return NextReviewResponse(
                concept_id=concept_id,
                next_review_at=None,
                current_mastery=None,
                total_exposures=0,
            )

        return NextReviewResponse(
            concept_id=concept_id,
            next_review_at=state.next_review_at,
            current_mastery=state.s_mastery,
            total_exposures=state.exposures,
        )
