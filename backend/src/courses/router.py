
"""Unified courses API router.

This router exposes the consolidated course API that replaces the legacy
course and lesson routes.

NOTE: Lesson, grading, frontier, practice drill, and review orchestration
is delegated to CoursesFacade; this module keeps HTTP-layer handling only.
"""

import logging
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status

from src.ai.service import AIService, get_ai_service
from src.auth import CurrentAuth
from src.courses.facade import CoursesFacade
from src.courses.schemas import (
    AttemptRequest,
    AttemptResponse,
    CodeExecuteRequest,
    CodeExecuteResponse,
    ConceptReviewRequest,
    CourseListResponse,
    CourseResponse,
    CourseUpdate,
    FrontierResponse,
    GradeRequest,
    GradeResponse,
    LessonDetailResponse,
    LessonNextPassRequest,
    LessonRegenerateRequest,
    LessonVersionHistoryResponse,
    NextReviewResponse,
    QuestionSetRequest,
    QuestionSetResponse,
    ReviewBatchResponse,
    RuntimeListRequest,
    RuntimeProcessInputRequest,
    RuntimeProcessReadRequest,
    RuntimeProcessStartRequest,
    RuntimeProcessStopRequest,
    RuntimeToolResponse,
    SelfAssessmentRequest,
    SelfAssessmentResponse,
)
from src.courses.services.code_execution_service import CodeExecutionError, CodeExecutionService, WorkspaceFile


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
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Topic must not be empty")

    level = request.level.strip() if request.level and request.level.strip() else None

    try:
        quiz = await ai_service.generate_self_assessment(
            topic=topic,
            level=level,
            user_id=auth.user_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error
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


class _InMemoryUploadFile:
    def __init__(self, filename: str, content_type: str, content: bytes) -> None:
        self.filename = filename
        self.content_type = content_type
        self.content = content

    async def read(self) -> bytes:
        return self.content


@router.post("/", status_code=status.HTTP_202_ACCEPTED)
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
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Prompt must not be empty")

    attachments = files or []
    in_memory_files = []
    for upload in attachments:
        if not upload.filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attachment filename required")
        ext = Path(upload.filename).suffix.lower()
        if ext not in _COURSE_ATTACHMENT_EXTENSIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported attachment type")
        content = await upload.read()
        in_memory_files.append(_InMemoryUploadFile(upload.filename, upload.content_type or "", content))

    return await facade.create_course(
        {"prompt": prompt_text, "adaptive_enabled": adaptive_enabled},
        auth.user_id,
        background_tasks=background_tasks,
        attachments=in_memory_files,
    )


@router.get("/")
async def list_courses(
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    per_page: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    search: Annotated[str | None, Query(description="Search query")] = None,
) -> CourseListResponse:
    """List courses with pagination and optional search (single source of truth)."""
    courses, total = await facade.list_courses(user_id=auth.user_id, page=page, per_page=per_page, search=search)
    return CourseListResponse(courses=courses, total=total, page=page, per_page=per_page)


@router.get("/{course_id}")
async def get_course(
    course_id: uuid.UUID,
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
) -> CourseResponse:
    """Get a specific course by ID."""
    return await facade.get_course(course_id, auth.user_id)


@router.patch("/{course_id}")
async def update_course(
    course_id: uuid.UUID,
    request: CourseUpdate,
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
) -> CourseResponse:
    """Update a course."""
    # Exclude None fields to avoid overwriting NOT NULL columns with NULL
    return await facade.update_course(course_id, auth.user_id, request.model_dump(exclude_none=True))


@router.get("/{course_id}/lessons/{lesson_id}")
async def get_lesson(
    course_id: uuid.UUID,
    lesson_id: uuid.UUID,
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
    generate: Annotated[bool, Query(description="Auto-generate if lesson doesn't exist")] = False,
    version_id: Annotated[
        uuid.UUID | None,
        Query(alias="versionId", description="Optional lesson version to read"),
    ] = None,
) -> LessonDetailResponse:
    """Get a specific lesson by course and lesson ID."""
    return await facade.get_lesson(
        course_id=course_id,
        lesson_id=lesson_id,
        user_id=auth.user_id,
        generate=generate,
        version_id=version_id,
    )


@router.get("/{course_id}/lessons/{lesson_id}/versions")
async def list_lesson_versions(
    course_id: uuid.UUID,
    lesson_id: uuid.UUID,
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
) -> LessonVersionHistoryResponse:
    """Return available version history for a lesson."""
    return await facade.list_lesson_versions(
        course_id=course_id,
        lesson_id=lesson_id,
        user_id=auth.user_id,
    )


@router.post("/{course_id}/lessons/{lesson_id}/regenerate")
async def regenerate_lesson(
    course_id: uuid.UUID,
    lesson_id: uuid.UUID,
    payload: LessonRegenerateRequest,
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
) -> LessonDetailResponse:
    """Regenerate a lesson using learner critique while keeping the same route identity."""
    return await facade.regenerate_lesson(
        course_id=course_id,
        lesson_id=lesson_id,
        critique_text=payload.critique_text,
        apply_across_course=payload.apply_across_course,
        user_id=auth.user_id,
    )


@router.post("/{course_id}/lessons/{lesson_id}/next-pass")
async def start_next_lesson_pass(
    course_id: uuid.UUID,
    lesson_id: uuid.UUID,
    payload: LessonNextPassRequest,
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
) -> LessonDetailResponse:
    """Create or select the next major lesson pass."""
    return await facade.start_next_lesson_pass(
        course_id=course_id,
        lesson_id=lesson_id,
        force=payload.force,
        user_id=auth.user_id,
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
    return await facade.grade_lesson_response(
        course_id=course_id,
        lesson_id=lesson_id,
        payload=payload,
        user_id=auth.user_id,
    )


@router.get("/{course_id}/concepts")
async def get_course_concept_frontier(
    course_id: uuid.UUID,
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
) -> FrontierResponse:
    """Return adaptive frontier data for a course."""
    return await facade.get_course_concept_frontier(
        course_id=course_id,
        user_id=auth.user_id,
    )


@router.post("/{course_id}/question-sets")
async def create_question_set(
    course_id: uuid.UUID,
    payload: QuestionSetRequest,
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
) -> QuestionSetResponse:
    """Create server-owned questions without exposing grading metadata."""
    return await facade.create_question_set(
        course_id=course_id,
        payload=payload,
        user_id=auth.user_id,
    )


@router.post("/{course_id}/attempts")
async def submit_attempt(
    course_id: uuid.UUID,
    payload: AttemptRequest,
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
) -> AttemptResponse:
    """Submit one answer and apply grading, mastery, and scheduling once."""
    return await facade.submit_attempt(
        course_id=course_id,
        payload=payload,
        user_id=auth.user_id,
    )


@router.post("/{course_id}/lessons/{lesson_id}/concept-reviews")
async def submit_concept_review(
    course_id: uuid.UUID,
    lesson_id: uuid.UUID,
    payload: ConceptReviewRequest,
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
) -> ReviewBatchResponse:
    """Submit one subjective learner self-rating for LECTOR scheduling."""
    return await facade.submit_concept_review(
        course_id=course_id,
        lesson_id=lesson_id,
        payload=payload,
        user_id=auth.user_id,
    )


@router.get("/{course_id}/concepts/{concept_id}/next-review")
async def get_concept_next_review(
    course_id: uuid.UUID,
    concept_id: uuid.UUID,
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
) -> NextReviewResponse:
    """Return the next scheduled review information for a concept."""
    return await facade.get_concept_next_review(
        course_id=course_id,
        concept_id=concept_id,
        user_id=auth.user_id,
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
            course = await facade.get_course(request.course_id, auth.user_id)
            setup_commands = course.setup_commands or []
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
    except (RuntimeError, OSError) as exc:
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


@router.post("/runtime/process/start")
async def runtime_start_process(
    request: RuntimeProcessStartRequest,
    auth: CurrentAuth,
    svc: Annotated[CodeExecutionService, Depends(get_code_execution_service)],
) -> RuntimeToolResponse:
    """Start a long-lived runtime process in the scoped sandbox."""
    try:
        data = await svc.start_process(
            command=request.command,
            user_id=str(auth.user_id),
            course_id=str(request.course_id) if request.course_id else None,
            workspace_id=request.workspace_id,
            cwd=request.cwd,
            env=request.env,
            user=request.user,
        )
    except CodeExecutionError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return RuntimeToolResponse(data=data)


@router.post("/runtime/process/output")
async def runtime_read_process_output(
    request: RuntimeProcessReadRequest,
    auth: CurrentAuth,
    svc: Annotated[CodeExecutionService, Depends(get_code_execution_service)],
) -> RuntimeToolResponse:
    """Read incremental output for a long-lived runtime process."""
    try:
        data = await svc.read_process_output(
            process_id=request.process_id,
            user_id=str(auth.user_id),
            course_id=str(request.course_id) if request.course_id else None,
            workspace_id=request.workspace_id,
        )
    except CodeExecutionError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return RuntimeToolResponse(data=data)


@router.post("/runtime/process/input")
async def runtime_send_process_input(
    request: RuntimeProcessInputRequest,
    auth: CurrentAuth,
    svc: Annotated[CodeExecutionService, Depends(get_code_execution_service)],
) -> RuntimeToolResponse:
    """Send stdin input to a long-lived runtime process."""
    try:
        data = await svc.send_process_input(
            process_id=request.process_id,
            input_text=request.input,
            user_id=str(auth.user_id),
            course_id=str(request.course_id) if request.course_id else None,
            workspace_id=request.workspace_id,
        )
    except CodeExecutionError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return RuntimeToolResponse(data=data)


@router.post("/runtime/process/stop")
async def runtime_stop_process(
    request: RuntimeProcessStopRequest,
    auth: CurrentAuth,
    svc: Annotated[CodeExecutionService, Depends(get_code_execution_service)],
) -> RuntimeToolResponse:
    """Stop a long-lived runtime process."""
    try:
        data = await svc.stop_process(
            process_id=request.process_id,
            user_id=str(auth.user_id),
            course_id=str(request.course_id) if request.course_id else None,
            workspace_id=request.workspace_id,
            wait_timeout_seconds=request.wait_timeout_seconds,
        )
    except CodeExecutionError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return RuntimeToolResponse(data=data)


@router.post("/runtime/list")
async def runtime_list_entries(
    request: RuntimeListRequest,
    auth: CurrentAuth,
    svc: Annotated[CodeExecutionService, Depends(get_code_execution_service)],
) -> RuntimeToolResponse:
    """List runtime filesystem entries for scoped lab/course sessions."""
    try:
        data = await svc.list_runtime_entries(
            path=request.path,
            depth=request.depth,
            user_id=str(auth.user_id),
            course_id=str(request.course_id) if request.course_id else None,
            workspace_id=request.workspace_id,
        )
    except CodeExecutionError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return RuntimeToolResponse(data=data)
