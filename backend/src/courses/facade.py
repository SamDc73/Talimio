
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

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from .models import Course, CourseConcept, Lesson
from .schemas import (
    FrontierResponse,
    GradeRequest,
    GradeResponse,
    LessonDetailResponse,
    NextReviewResponse,
    PracticeDrillResponse,
    ReviewBatchRequest,
    ReviewBatchResponse,
    ReviewOutcome,
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


class CoursesFacadeError(Exception):
    """Domain exception raised by course facade operations."""

    def __init__(self, detail: Any, status_code: int) -> None:
        super().__init__(str(detail))
        self.detail = detail
        self.status_code = status_code


class CoursesFacadeNotFoundError(CoursesFacadeError):
    """Facade error for missing course resources."""

    def __init__(self, detail: str = "Resource not found") -> None:
        super().__init__(detail=detail, status_code=status.HTTP_404_NOT_FOUND)


class CoursesFacadeBadRequestError(CoursesFacadeError):
    """Facade error for invalid domain state transitions."""

    def __init__(self, detail: str = "Invalid request") -> None:
        super().__init__(detail=detail, status_code=status.HTTP_400_BAD_REQUEST)


class CoursesFacadeValidationError(CoursesFacadeError):
    """Facade error for payload validation mismatches."""

    def __init__(self, detail: str = "Validation failed") -> None:
        super().__init__(detail=detail, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


class CoursesFacadeUpstreamError(CoursesFacadeError):
    """Facade error for upstream provider failures."""

    def __init__(self, detail: str = "Upstream request failed") -> None:
        super().__init__(detail=detail, status_code=status.HTTP_502_BAD_GATEWAY)


class CoursesFacade:
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
        """
        Get course with progress information.

        Implements ContentFacade interface for consistent cross-module API.
        """
        return await self.get_course(content_id, user_id)

    async def get_course(
        self,
        course_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> dict[str, Any]:
        """
        Get complete course information with progress.

        Coordinates course service and progress service to provide comprehensive data.
        """
        try:
            query_service = CourseQueryService(self._session)
            course_response = await query_service.get_course(course_id, user_id)

            course = course_response.model_dump() if course_response else None
            if not course:
                return {"error": "Course not found", "success": False}

            # Get progress data from progress service
            progress = await self._progress_service.get_progress(course_id, user_id)
            completion_percentage = progress.get("completion_percentage", 0)
            completed_lessons = progress.get("completed_lessons", {})
            current_lesson = progress.get("current_lesson", "")
            total_lessons = progress.get("total_lessons", 0)

            return {
                "course": course,
                "progress": progress,
                "completion_percentage": completion_percentage,
                "current_lesson": current_lesson,
                "total_lessons": total_lessons,
                "completed_lessons": completed_lessons,
                "success": True,
            }

        except HTTPException as exc:
            if exc.status_code == 404:
                return {"error": "Course not found", "success": False}
            logger.exception("Error getting course %s for user %s", course_id, user_id)
            return {"error": "Failed to retrieve course", "success": False}

        except (SQLAlchemyError, RuntimeError, ValueError, TypeError):
            logger.exception("Error getting course %s for user %s", course_id, user_id)
            return {"error": "Failed to retrieve course", "success": False}

    async def create_course(
        self,
        course_data: dict[str, Any],
        user_id: uuid.UUID,
        background_tasks: BackgroundTasks | None = None,
        attachments: list[Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create new course entry.

        Handles course creation and coordinates all related operations.
        """
        try:
            # Use the content service which handles tags, progress, and AI processing
            created_course = await self._content_service.create_course(
                course_data,
                user_id,
                background_tasks=background_tasks,
                attachments=attachments,
            )

            query_service = CourseQueryService(self._session)
            course_response = await query_service.get_course(created_course.id, user_id)

            return {"course": course_response, "success": True}

        except (HTTPException, SQLAlchemyError, RuntimeError, ValueError, TypeError):
            logger.exception("Error creating course for user %s", user_id)
            return {"error": "Failed to create course", "success": False}

    # NOTE: Auto-tagging removed - now handled by CourseContentService via BaseContentService pipeline
    # Tagging happens automatically during course creation/updates, no manual intervention needed

    async def generate_ai_course(
        self,
        topic: str,
        preferences: dict[str, Any],
        user_id: uuid.UUID,
        background_tasks: BackgroundTasks | None = None,
    ) -> dict[str, Any]:
        """
        Generate AI-powered course from topic.

        Handles AI course generation and coordinates related operations.
        """
        try:
            # Build course data combining provided preferences and required fields
            data: dict[str, Any] = {**(preferences or {})}
            data["prompt"] = topic  # Use prompt field for AI generation

            # Use the content service which handles tags, progress, and AI processing automatically
            course = await self._content_service.create_course(
                data,
                user_id,
                background_tasks=background_tasks,
            )

            query_service = CourseQueryService(self._session)
            course_response = await query_service.get_course(course.id, user_id)

            return {"course": course_response, "success": True}

        except (HTTPException, SQLAlchemyError, RuntimeError, ValueError, TypeError) as e:
            logger.exception("Error generating AI course %s for user %s: %s", topic, user_id, e)
            return {"error": f"Failed to generate course: {e!s}", "success": False}

    async def update_progress(self, content_id: uuid.UUID, user_id: uuid.UUID, progress_data: dict[str, Any]) -> dict[str, Any]:
        """
        Update course progress.

        Implements ContentFacade interface.
        """
        return await self.update_course_progress(content_id, user_id, progress_data)

    async def update_course_progress(
        self, course_id: uuid.UUID, user_id: uuid.UUID, progress_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Update course progress.

        Handles progress updates, lesson tracking, and completion detection.
        """
        try:
            updated_progress = await self._progress_service.update_progress(course_id, user_id, progress_data)
            return {"progress": updated_progress, "success": True}

        except (SQLAlchemyError, RuntimeError, ValueError, TypeError) as e:
            logger.exception("Error updating progress for course %s: %s", course_id, e)
            return {"error": f"Failed to update progress: {e!s}", "success": False}

    async def update_course(self, course_id: uuid.UUID, user_id: uuid.UUID, update_data: dict[str, Any]) -> dict[str, Any]:
        """Update course metadata."""
        try:
            # Update through content service which handles tags and reprocessing
            updated_course = await self._content_service.update_course(course_id, update_data, user_id)

            query_service = CourseQueryService(self._session)
            course_response = await query_service.get_course(updated_course.id, user_id)

            return {"course": course_response, "success": True}

        except (HTTPException, SQLAlchemyError, RuntimeError, ValueError, TypeError):
            logger.exception("Error updating course %s", course_id)
            return {"error": "Failed to update course", "success": False}

    async def list_courses(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        per_page: int = 20,
        search: str | None = None,
    ) -> dict[str, Any]:
        """List user courses with pagination and optional search."""
        try:
            query_service = CourseQueryService(self._session)
            courses, total = await query_service.list_courses(
                page=page,
                per_page=per_page,
                search=search,
                user_id=user_id,
            )
            return {"courses": courses, "total": total, "success": True}
        except (SQLAlchemyError, RuntimeError, ValueError, TypeError):
            logger.exception("Error listing courses for user %s", user_id)
            return {"error": "Failed to list courses", "success": False}

    async def search_courses(self, query: str, user_id: uuid.UUID, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Search user's courses.

        Provides unified search across course content and metadata.
        """
        try:
            query_service = CourseQueryService(self._session)
            limit = (filters or {}).get("limit", 20)
            results, _total = await query_service.list_courses(per_page=limit, search=query, user_id=user_id)

            return {"results": results, "success": True}

        except (SQLAlchemyError, RuntimeError, ValueError, TypeError):
            logger.exception("Error searching courses for user %s", user_id)
            return {"error": "Search failed", "success": False}

    async def get_user_courses(self, user_id: uuid.UUID, include_progress: bool = True) -> dict[str, Any]:
        """
        Get all courses for user.

        Optionally includes progress information.
        """
        try:
            query_service = CourseQueryService(self._session)
            # Keep pagination aligned with API defaults to avoid oversized payloads.
            per_page = 20
            course_responses, _total = await query_service.list_courses(
                page=1, per_page=per_page, search=None, user_id=user_id
            )

            course_dicts: list[dict[str, Any]] = []
            for cr in course_responses:
                cd = cr.model_dump()
                if include_progress:
                    try:
                        progress = await self._progress_service.get_progress(cr.id, user_id)
                        cd["progress"] = progress
                    except (RuntimeError, ValueError) as e:
                        logger.warning("Failed to get progress for course %s: %s", cr.id, e)
                        cd["progress"] = {"completion_percentage": 0, "completed_lessons": {}}
                course_dicts.append(cd)

            return {"courses": course_dicts, "success": True}

        except (SQLAlchemyError, RuntimeError, ValueError, TypeError) as e:
            logger.exception("Error getting courses for user %s: %s", user_id, e)
            return {"error": f"Failed to get courses: {e!s}", "success": False}

    async def get_course_lessons(self, course_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, Any]:
        """Get course lessons grouped by modules."""
        try:
            try:
                query_service = CourseQueryService(self._session)
                course_response = await query_service.get_course(course_id, user_id)
            except HTTPException as exc:
                if exc.status_code == 404:
                    logger.info("Course %s not found for user %s", course_id, user_id)
                    return {"error": f"Course {course_id} not found", "success": False}
                raise

            progress = await self._progress_service.get_progress(course_id, user_id)
            completed_lessons = progress.get("completed_lessons", {}) if isinstance(progress, dict) else {}

            lessons_payload: list[dict[str, Any]] = []
            for module in course_response.modules:
                for lesson in module.lessons:
                    lesson_dict = lesson.model_dump()
                    lesson_dict["moduleTitle"] = module.title
                    lesson_dict["moduleId"] = str(module.id)
                    lesson_dict["completed"] = completed_lessons.get(str(lesson.id), False)
                    lessons_payload.append(lesson_dict)

            return {"lessons": lessons_payload, "success": True}

        except (HTTPException, SQLAlchemyError, RuntimeError, ValueError, TypeError):
            logger.exception("Error getting lessons for course %s", course_id)
            return {"error": "Failed to get lessons", "success": False}

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
    ) -> LessonDetailResponse:
        """Get a lesson detail payload for an owned course."""
        lesson_service = LessonService(self._session, user_id)
        try:
            return await lesson_service.get_lesson(course_id, lesson_id, force_refresh=generate)
        except HTTPException as exc:
            raise CoursesFacadeError(detail=exc.detail, status_code=exc.status_code) from exc

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

        lesson_exists = await self._session.scalar(
            select(Lesson.id).where(
                Lesson.id == lesson_id,
                Lesson.course_id == course_id,
            )
        )
        if lesson_exists is None:
            detail = "Lesson not found"
            raise CoursesFacadeNotFoundError(detail)

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
        return await grading_service.grade(payload, user_id)

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
            user_id=user_id,
            course_id=course_id,
            graph_service=graph_service,
            scheduler_service=scheduler_service,
        )

    async def generate_practice_drills(
        self,
        *,
        course_id: uuid.UUID,
        concept_id: uuid.UUID,
        count: int,
        user_id: uuid.UUID,
    ) -> PracticeDrillResponse:
        """Generate adaptive drill items for one concept in an owned course."""
        course = await self._require_owned_course(course_id=course_id, user_id=user_id)
        if not course.adaptive_enabled:
            detail = "Adaptive scheduling is not enabled for this course"
            raise CoursesFacadeBadRequestError(detail)

        drill_service = PracticeDrillService(self._session)
        try:
            drills = await drill_service.generate_drills(
                user_id=user_id,
                course_id=course.id,
                concept_id=concept_id,
                count=count,
            )
        except LookupError as error:
            raise CoursesFacadeNotFoundError(str(error)) from error
        except ValueError as error:
            raise CoursesFacadeValidationError(str(error)) from error
        except (RuntimeError, TypeError) as error:
            logger.exception(
                "PRACTICE_DRILL_GENERATION_FAILED",
                extra={
                    "course_id": str(course.id),
                    "user_id": str(user_id),
                    "concept_id": str(concept_id),
                    "count": count,
                },
            )
            detail = "Failed to generate practice drills"
            raise CoursesFacadeUpstreamError(detail) from error

        return PracticeDrillResponse(drills=drills)

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
