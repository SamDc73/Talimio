"""Unified courses API router.

This router exposes the consolidated course API that replaces the legacy
course and lesson routes.

NOTE: This router has been fully migrated to use CoursesFacade.
CoursesFacade now handles all endpoints including lesson-specific operations.
"""

import logging
from datetime import UTC, datetime
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.service import AIService, get_ai_service
from src.auth import CurrentAuth
from src.courses.facade import CoursesFacade
from src.courses.models import Course, CourseConcept
from src.courses.schemas import (
    CodeExecuteRequest,
    CodeExecuteResponse,
    CourseCreate,
    CourseListResponse,
    CourseResponse,
    CourseUpdate,
    FrontierResponse,
    LessonDetailResponse,
    MDXValidateRequest,
    MDXValidateResponse,
    NextReviewResponse,
    ReviewBatchRequest,
    ReviewBatchResponse,
    ReviewOutcome,
    SelfAssessmentRequest,
    SelfAssessmentResponse,
)
from src.courses.services.code_execution_service import CodeExecutionError, CodeExecutionService, WorkspaceFile
from src.courses.services.concept_graph_service import ConceptGraphService
from src.courses.services.concept_scheduler_service import LectorSchedulerService
from src.courses.services.concept_state_service import ConceptStateService
from src.courses.services.course_progress_service import CourseProgressService
from src.courses.services.course_query_service import CourseQueryService
from src.courses.services.frontier_builder import build_course_frontier
from src.courses.services.lesson_service import LessonService
from src.courses.services.mdx_service import mdx_service
from src.database.session import get_db_session
from src.middleware.security import ai_rate_limit


router = APIRouter(
    prefix="/api/v1/courses",
    tags=["courses"],
    responses={404: {"description": "Not found"}},
)


# Local logger for analytics
logger = logging.getLogger(__name__)


def get_courses_facade() -> CoursesFacade:
    """Get courses facade instance."""
    return CoursesFacade()


def get_lesson_service(
    auth: CurrentAuth,
    session: AsyncSession = Depends(get_db_session),
) -> LessonService:
    """Get lesson service instance with user_id injection."""
    return LessonService(session, auth.user_id)


def get_code_execution_service() -> CodeExecutionService:
    """Get code execution service instance."""
    return CodeExecutionService()


def get_ai_service_dependency() -> AIService:
    """Provide AI service singleton for dependency injection."""
    return get_ai_service()


async def _get_course_or_404(
    session: AsyncSession,
    course_id: UUID,
    user_id: UUID,
) -> Course:
    """Load course ensuring ownership, else raise 404."""
    course = await session.get(Course, course_id)
    if course is None or course.user_id != user_id:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


# Course operations
@router.post("/self-assessment/questions")
async def generate_self_assessment_questions(
    request: SelfAssessmentRequest,
    auth: CurrentAuth,
    ai_service: Annotated[AIService, Depends(get_ai_service_dependency)],
) -> SelfAssessmentResponse:
    """Return optional self-assessment questions for course personalization."""
    topic = request.topic.strip()
    if not topic:
        raise HTTPException(status_code=422, detail="Topic must not be empty")

    level = request.level.strip() if request.level and request.level.strip() else None

    try:
        quiz = await ai_service.generate_self_assessment(
            topic=topic,
            level=level,
            user_id=auth.user_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        logger.exception(
            "SELF_ASSESSMENT_GENERATION_FAILED",
            extra={
                "user_id": str(auth.user_id),
                "topic": topic,
            },
        )
        raise HTTPException(status_code=502, detail="Failed to generate self-assessment questions") from error

    return SelfAssessmentResponse.model_validate(quiz.model_dump())


@router.post("/")
async def create_course(
    request: CourseCreate,
    auth: CurrentAuth,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
) -> CourseResponse:
    """Create a new course using AI generation."""
    result = await facade.create_course(
        request.model_dump(),
        auth.user_id,
        session=session,
        background_tasks=background_tasks,
    )
    if not result.get("success"):
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=result.get("error", "Failed to create course"))

    return result["course"]


@router.get("/")
async def list_courses(
    auth: CurrentAuth,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    per_page: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    search: Annotated[str | None, Query(description="Search query")] = None,
) -> CourseListResponse:
    """List courses with pagination and optional search (single source of truth)."""
    qs = CourseQueryService(session)
    courses, total = await qs.list_courses(page=page, per_page=per_page, search=search, user_id=auth.user_id)
    return CourseListResponse(courses=courses, total=total, page=page, per_page=per_page)


@router.get("/{course_id}")
async def get_course(
    course_id: UUID,
    auth: CurrentAuth,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
) -> CourseResponse:
    """Get a specific course by ID."""
    result = await facade.get_course(course_id, auth.user_id, session=session)

    if not result.get("success"):
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=result.get("error", "Course not found"))

    return result["course"]


@router.patch("/{course_id}")
async def update_course(
    course_id: UUID,
    request: CourseUpdate,
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
) -> CourseResponse:
    """Update a course."""
    # Exclude None fields to avoid overwriting NOT NULL columns with NULL
    result = await facade.update_course(course_id, auth.user_id, request.model_dump(exclude_none=True))

    if not result.get("success"):
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=result.get("error", "Failed to update course"))

    return result["course"]


@router.get("/{course_id}/lessons/{lesson_id}")
async def get_lesson(
    course_id: UUID,
    lesson_id: UUID,
    lesson_service: Annotated[LessonService, Depends(get_lesson_service)],
    generate: Annotated[bool, Query(description="Auto-generate if lesson doesn't exist")] = False,
) -> LessonDetailResponse:
    """Get a specific lesson by course and lesson ID."""
    return await lesson_service.get_lesson(course_id, lesson_id, force_refresh=generate)


@router.get("/{course_id}/concepts")
async def get_course_concept_frontier(
    course_id: UUID,
    auth: CurrentAuth,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FrontierResponse:
    """Return adaptive frontier data for a course."""
    course = await _get_course_or_404(session, course_id, auth.user_id)
    if not course.adaptive_enabled:
        return FrontierResponse(
            frontier=[],
            due_for_review=[],
            coming_soon=[],
            due_count=0,
            avg_mastery=0.0,
        )

    graph_service = ConceptGraphService(session)
    scheduler_service = LectorSchedulerService(session)
    return await build_course_frontier(
        user_id=auth.user_id,
        course_id=course_id,
        graph_service=graph_service,
        scheduler_service=scheduler_service,
    )


@router.post("/{course_id}/lessons/{lesson_id}/reviews")
async def submit_adaptive_reviews(
    course_id: UUID,
    lesson_id: UUID,
    payload: ReviewBatchRequest,
    auth: CurrentAuth,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ReviewBatchResponse:
    """Submit concept reviews for LECTOR scheduling."""
    if not payload.reviews:
        raise HTTPException(status_code=422, detail="At least one review is required")

    course = await _get_course_or_404(session, course_id, auth.user_id)
    if not course.adaptive_enabled:
        raise HTTPException(status_code=400, detail="Adaptive scheduling is not enabled for this course")

    concept_ids = {review.concept_id for review in payload.reviews}
    existing = await session.execute(
        select(CourseConcept.concept_id).where(
            CourseConcept.course_id == course.id,
            CourseConcept.concept_id.in_(concept_ids),
        )
    )
    found_ids = set(existing.scalars().all())
    missing = concept_ids - found_ids
    if missing:
        raise HTTPException(status_code=404, detail="One or more concepts are not assigned to this course")

    state_service = ConceptStateService(session)
    scheduler_service = LectorSchedulerService(session)

    outcomes: list[ReviewOutcome] = []
    concept_stats: dict[str, dict[str, Any]] = {}
    last_review_snapshot: dict[str, Any] | None = None

    for review in payload.reviews:
        correct = review.rating >= 3
        updated_state = await state_service.update_mastery(
            user_id=auth.user_id,
            concept_id=review.concept_id,
            correct=correct,
            latency_ms=review.latency_ms,
        )
        await state_service.log_probe_event(
            user_id=auth.user_id,
            concept_id=review.concept_id,
            rating=review.rating,
            review_duration_ms=review.review_duration_ms,
            correct=correct,
            latency_ms=review.latency_ms,
            context_tag=f"lesson:{lesson_id}",
            extra={"rating": review.rating},
        )
        next_review = await scheduler_service.calculate_next_review(
            user_id=auth.user_id,
            course_id=course.id,
            concept_id=review.concept_id,
            rating=review.rating,
            duration_ms=review.review_duration_ms,
        )
        await scheduler_service.update_learner_profile(
            user_id=auth.user_id,
            concept_id=review.concept_id,
            rating=review.rating,
            duration_ms=review.review_duration_ms,
        )

        outcomes.append(
            ReviewOutcome(
                concept_id=review.concept_id,
                next_review_at=next_review,
                mastery=updated_state.s_mastery,
                exposures=updated_state.exposures,
            )
        )

        concept_key = str(review.concept_id)
        stats = concept_stats.setdefault(
            concept_key,
            {
                "ratingCounts": {"1": 0, "2": 0, "3": 0, "4": 0},
                "totalDurationMs": 0,
            },
        )
        rating_counts = cast("dict[str, int]", stats["ratingCounts"])
        rating_key = str(review.rating)
        rating_counts[rating_key] = rating_counts.get(rating_key, 0) + 1
        stats["totalDurationMs"] = int(stats["totalDurationMs"]) + int(review.review_duration_ms)
        stats.update(
            {
                "lastRating": review.rating,
                "lastDurationMs": review.review_duration_ms,
                "lastReviewedAt": datetime.now(UTC).isoformat(),
                "lastNextReviewAt": next_review.isoformat() if next_review else None,
                "mastery": float(updated_state.s_mastery or 0.0),
                "exposures": int(updated_state.exposures),
            }
        )
        last_review_snapshot = {
            "concept_id": concept_key,
            "rating": review.rating,
            "duration_ms": review.review_duration_ms,
            "next_review_at": next_review.isoformat() if next_review else None,
        }

    await session.commit()

    if last_review_snapshot is not None:
        progress_payload: dict[str, Any] = {
            "current_lesson": str(lesson_id),
            "last_reviewed_concept": last_review_snapshot["concept_id"],
            "last_reviewed_rating": last_review_snapshot["rating"],
            "last_review_duration_ms": last_review_snapshot["duration_ms"],
            "last_reviewed_at": datetime.now(UTC).isoformat(),
            "last_next_review_at": last_review_snapshot["next_review_at"],
            "concept_review_stats": concept_stats,
        }
        try:
            progress_service = CourseProgressService(session)
            await progress_service.update_progress(course.id, auth.user_id, progress_payload)
        except Exception:  # pragma: no cover - diagnostic logging only
            logger.exception(
                "COURSE_PROGRESS_UPDATE_FAILED",
                extra={
                    "course_id": str(course.id),
                    "user_id": str(auth.user_id),
                    "lesson_id": str(lesson_id),
                },
            )

    return ReviewBatchResponse(outcomes=outcomes)


@router.get("/{course_id}/concepts/{concept_id}/next-review")
async def get_concept_next_review(
    course_id: UUID,
    concept_id: UUID,
    auth: CurrentAuth,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> NextReviewResponse:
    """Return the next scheduled review information for a concept."""
    course = await _get_course_or_404(session, course_id, auth.user_id)
    if not course.adaptive_enabled:
        raise HTTPException(status_code=400, detail="Adaptive scheduling is not enabled for this course")

    linkage = await session.execute(
        select(CourseConcept.concept_id).where(
            CourseConcept.course_id == course.id,
            CourseConcept.concept_id == concept_id,
        )
    )
    if linkage.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Concept is not assigned to this course")

    state_service = ConceptStateService(session)
    state = await state_service.get_user_concept_state(
        user_id=auth.user_id,
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


# NOTE: Quiz submission removed - quizzes are part of lesson content and handled via lesson progress updates
# Quiz results should be submitted through the lesson status update endpoints, not as separate entities


# MDX validation endpoint
@router.post("/validate-mdx")
async def validate_mdx(request: MDXValidateRequest) -> MDXValidateResponse:
    """
    Validate MDX content syntax.

    This endpoint validates MDX content before it's stored or processed,
    ensuring proper syntax for JSX components, markdown, and exports.
    """
    is_valid, error = mdx_service.validate_mdx(request.content)

    # Extract metadata if valid
    metadata = None
    if is_valid:
        metadata = mdx_service.extract_metadata(request.content)

    return MDXValidateResponse(valid=is_valid, error=error, metadata=metadata)


# --- Code Execution (E2B) ---
@ai_rate_limit
@router.post("/code/execute")
async def execute_code(
    request: CodeExecuteRequest,
    auth: CurrentAuth,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    svc: Annotated[CodeExecutionService, Depends(get_code_execution_service)],
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
) -> CodeExecuteResponse:
    """Execute a single code snippet via E2B sandbox.

    Auth is required; minimal logging/analytics.
    Uses course-scoped sandboxes with setup_commands for fast execution.
    """
    # Fetch setup_commands from course if course_id provided
    setup_commands: list[str] = []
    if request.course_id:
        try:
            result = await facade.get_course(request.course_id, auth.user_id, session=session)
            if result.get("success") and "course" in result:
                course = result["course"]
                setup_commands = course.setup_commands or []
        except Exception:
            logger.debug("Could not fetch course setup_commands for course_id=%s", request.course_id)

    workspace_files: list[WorkspaceFile] | None = None
    if request.files:
        workspace_files = [WorkspaceFile(path=item.path, content=item.content) for item in request.files]

    try:
        result = await svc.execute(
            source_code=request.code,
            language=request.language,
            stdin=request.stdin,
            user_id=str(auth.user_id),
            course_id=str(request.course_id) if request.course_id else None,
            lesson_id=str(request.lesson_id) if request.lesson_id else None,
            setup_commands=setup_commands,
            files=workspace_files,
            entry_file=request.entry_file,
            workspace_id=request.workspace_id,
        )
    except CodeExecutionError as error:
        logger.warning(
            "CODE_EXECUTION_ERROR",
            extra={
                "user_id": str(auth.user_id),
                "lesson_id": str(request.lesson_id) if request.lesson_id else None,
                "language": request.language,
                "error_code": error.error_code,
            },
        )
        detail = f"{error} (code: {error.error_code})"
        raise HTTPException(status_code=error.status_code, detail=detail) from error
    except ValueError as exc:
        logger.warning(
            "CODE_EXECUTION_INVALID_INPUT",
            extra={
                "user_id": str(auth.user_id),
                "lesson_id": str(request.lesson_id) if request.lesson_id else None,
                "language": request.language,
            },
            exc_info=True,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "CODE_EXECUTION_UNEXPECTED",
            extra={
                "user_id": str(auth.user_id),
                "lesson_id": str(request.lesson_id) if request.lesson_id else None,
                "language": request.language,
            },
        )
        raise HTTPException(status_code=502, detail="Execution failed") from exc

    response = CodeExecuteResponse(
        stdout=result.stdout,
        stderr=result.stderr,
        status=result.status,
        time=result.time,
        memory=result.memory,
    )

    # Minimal analytics log
    logger.info(
        "CODE_EXECUTION",
        extra={
            "user_id": str(auth.user_id),
            "lesson_id": str(request.lesson_id) if request.lesson_id else None,
            "language": request.language,
            "status": response.status,
            "time": response.time,
            "memory": response.memory,
        },
    )

    return response
