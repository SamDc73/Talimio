
"""Unified courses API router.

This router exposes the consolidated course API that replaces the legacy
course and lesson routes.

NOTE: Lesson, grading, frontier, practice drill, and review orchestration
is delegated to CoursesFacade; this module keeps HTTP-layer handling only.
"""

import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status

from src.ai.service import AIService, get_ai_service
from src.auth import CurrentAuth
from src.courses.facade import CoursesFacade, CoursesFacadeError
from src.courses.schemas import (
    CodeExecuteRequest,
    CodeExecuteResponse,
    CourseListResponse,
    CourseResponse,
    CourseUpdate,
    FrontierResponse,
    GradeRequest,
    GradeResponse,
    LessonDetailResponse,
    NextReviewResponse,
    PracticeDrillRequest,
    PracticeDrillResponse,
    ReviewBatchRequest,
    ReviewBatchResponse,
    SelfAssessmentRequest,
    SelfAssessmentResponse,
)
from src.courses.services.code_execution_service import CodeExecutionError, CodeExecutionService, WorkspaceFile


if TYPE_CHECKING:
    from collections.abc import Awaitable


router = APIRouter(
    prefix="/api/v1/courses",
    tags=["courses"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


# Local logger for analytics
logger = logging.getLogger(__name__)

_COURSE_ATTACHMENT_EXTENSIONS = {".pdf", ".epub", ".png", ".jpg", ".jpeg"}


def get_courses_facade(auth: CurrentAuth) -> CoursesFacade:
    """Get courses facade instance."""
    return CoursesFacade(auth.session)


def get_code_execution_service(auth: CurrentAuth) -> CodeExecutionService:
    """Get code execution service instance."""
    return CodeExecutionService(auth.session)


def get_ai_service_dependency() -> AIService:
    """Provide AI service singleton for dependency injection."""
    return get_ai_service()


async def _call_courses_facade[T](operation: Awaitable[T]) -> T:
    """Execute a facade operation and map facade errors to HTTP responses."""
    try:
        return await operation
    except CoursesFacadeError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


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
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Topic must not be empty")

    level = request.level.strip() if request.level and request.level.strip() else None

    try:
        quiz = await ai_service.generate_self_assessment(
            topic=topic,
            level=level,
            user_id=auth.user_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    except (RuntimeError, TypeError) as error:
        logger.exception(
            "SELF_ASSESSMENT_GENERATION_FAILED",
            extra={
                "user_id": str(auth.user_id),
                "topic": topic,
            },
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to generate self-assessment questions") from error

    return SelfAssessmentResponse.model_validate(quiz.model_dump())


@router.post("/")
async def create_course(
    prompt: Annotated[str, Form()],
    auth: CurrentAuth,
    background_tasks: BackgroundTasks,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
    adaptive_enabled: Annotated[bool, Form()] = False,
    files: Annotated[list[UploadFile] | None, File()] = None,
) -> CourseResponse:
    """Create a new course using AI generation."""
    prompt_text = prompt.strip()
    if not prompt_text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Prompt must not be empty")

    attachments = files or []
    for upload in attachments:
        if not upload.filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attachment filename required")
        ext = Path(upload.filename).suffix.lower()
        if ext not in _COURSE_ATTACHMENT_EXTENSIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported attachment type")

    result = await facade.create_course(
        {"prompt": prompt_text, "adaptive_enabled": adaptive_enabled},
        auth.user_id,
        background_tasks=background_tasks,
        attachments=attachments,
    )
    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("error", "Failed to create course"))

    return result["course"]


@router.get("/")
async def list_courses(
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    per_page: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    search: Annotated[str | None, Query(description="Search query")] = None,
) -> CourseListResponse:
    """List courses with pagination and optional search (single source of truth)."""
    result = await facade.list_courses(user_id=auth.user_id, page=page, per_page=per_page, search=search)
    if not result.get("success"):
        detail = result.get("error", "Failed to list courses")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)

    courses = result.get("courses", [])
    total = result.get("total", 0)
    return CourseListResponse(courses=courses, total=total, page=page, per_page=per_page)


@router.get("/{course_id}")
async def get_course(
    course_id: uuid.UUID,
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
) -> CourseResponse:
    """Get a specific course by ID."""
    result = await facade.get_course(course_id, auth.user_id)

    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.get("error", "Course not found"))

    return result["course"]


@router.patch("/{course_id}")
async def update_course(
    course_id: uuid.UUID,
    request: CourseUpdate,
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
) -> CourseResponse:
    """Update a course."""
    # Exclude None fields to avoid overwriting NOT NULL columns with NULL
    result = await facade.update_course(course_id, auth.user_id, request.model_dump(exclude_none=True))

    if not result.get("success"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("error", "Failed to update course"))

    return result["course"]


@router.get("/{course_id}/lessons/{lesson_id}")
async def get_lesson(
    course_id: uuid.UUID,
    lesson_id: uuid.UUID,
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
    generate: Annotated[bool, Query(description="Auto-generate if lesson doesn't exist")] = False,
) -> LessonDetailResponse:
    """Get a specific lesson by course and lesson ID."""
    return await _call_courses_facade(
        facade.get_lesson(
            course_id=course_id,
            lesson_id=lesson_id,
            user_id=auth.user_id,
            generate=generate,
        )
    )


@router.post("/{course_id}/lessons/{lesson_id}/grade")
async def grade_lesson_response(
    course_id: uuid.UUID,
    lesson_id: uuid.UUID,
    payload: GradeRequest,
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
) -> GradeResponse:
    """Grade a learner response for a lesson."""
    return await _call_courses_facade(
        facade.grade_lesson_response(
            course_id=course_id,
            lesson_id=lesson_id,
            payload=payload,
            user_id=auth.user_id,
        )
    )


@router.get("/{course_id}/concepts")
async def get_course_concept_frontier(
    course_id: uuid.UUID,
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
) -> FrontierResponse:
    """Return adaptive frontier data for a course."""
    return await _call_courses_facade(
        facade.get_course_concept_frontier(
            course_id=course_id,
            user_id=auth.user_id,
        )
    )


@router.post("/{course_id}/practice/drills")
async def generate_practice_drills(
    course_id: uuid.UUID,
    payload: PracticeDrillRequest,
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
) -> PracticeDrillResponse:
    """Generate adaptive drill items for one concept."""
    return await _call_courses_facade(
        facade.generate_practice_drills(
            course_id=course_id,
            concept_id=payload.concept_id,
            count=payload.count,
            user_id=auth.user_id,
        )
    )


@router.post("/{course_id}/lessons/{lesson_id}/reviews")
async def submit_adaptive_reviews(
    course_id: uuid.UUID,
    lesson_id: uuid.UUID,
    payload: ReviewBatchRequest,
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
) -> ReviewBatchResponse:
    """Submit concept reviews for LECTOR scheduling."""
    return await _call_courses_facade(
        facade.submit_adaptive_reviews(
            course_id=course_id,
            lesson_id=lesson_id,
            payload=payload,
            user_id=auth.user_id,
        )
    )


@router.get("/{course_id}/concepts/{concept_id}/next-review")
async def get_concept_next_review(
    course_id: uuid.UUID,
    concept_id: uuid.UUID,
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
) -> NextReviewResponse:
    """Return the next scheduled review information for a concept."""
    return await _call_courses_facade(
        facade.get_concept_next_review(
            course_id=course_id,
            concept_id=concept_id,
            user_id=auth.user_id,
        )
    )


# NOTE: Quiz submission removed - quizzes are part of lesson content and handled via lesson progress updates
# Quiz results should be submitted through the lesson status update endpoints, not as separate entities


# --- Code Execution (E2B) ---
@router.post("/code/execute")
async def execute_code(
    request: CodeExecuteRequest,
    auth: CurrentAuth,
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
            result = await facade.get_course(request.course_id, auth.user_id)
            if result.get("success") and "course" in result:
                course = result["course"]
                setup_commands = course.get("setup_commands") or []
        except (RuntimeError, ValueError):
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
        error_detail = str(error).strip() or "Code execution failed"
        detail = f"{error_detail} (code: {error.error_code})"
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except (RuntimeError, OSError, TimeoutError) as exc:
        logger.exception(
            "CODE_EXECUTION_UNEXPECTED",
            extra={
                "user_id": str(auth.user_id),
                "lesson_id": str(request.lesson_id) if request.lesson_id else None,
                "language": request.language,
            },
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Execution failed") from exc

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
