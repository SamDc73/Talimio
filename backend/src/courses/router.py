
"""Unified courses API router.

This router exposes the consolidated course API that replaces the legacy
course and lesson routes.

NOTE: Lesson, grading, frontier, practice drill, and review orchestration
is delegated to CoursesFacade; this module keeps HTTP-layer handling only.
"""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.ai.service import AIService, get_ai_service
from src.auth import CurrentAuth
from src.courses.facade import CoursesFacade
from src.courses.schemas import (
    AttemptRequest,
    AttemptResponse,
    CodeExecuteRequest,
    CodeExecuteResponse,
    ConceptReviewRequest,
    CourseAttachmentBulkCreate,
    CourseAttachmentRead,
    CourseCreateRequest,
    CourseListResponse,
    CourseResponse,
    CourseUpdate,
    FrontierResponse,
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
from src.courses.services.code_execution_service import CodeExecutionService, WorkspaceFile
from src.courses.services.course_attachments_service import CourseAttachmentsService


router = APIRouter(
    prefix="/api/v1/courses",
    tags=["courses"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)


# Local logger for analytics
logger = logging.getLogger(__name__)


def get_courses_facade(auth: CurrentAuth) -> CoursesFacade:
    """Get courses facade instance."""
    return CoursesFacade(auth.session)


def get_code_execution_service(auth: CurrentAuth) -> CodeExecutionService:
    """Get code execution service instance."""
    return CodeExecutionService(auth.session)


def get_course_attachments_service(auth: CurrentAuth) -> CourseAttachmentsService:
    """Get course attachments service instance."""
    return CourseAttachmentsService(auth.session)


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


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_course(
    request: CourseCreateRequest,
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
) -> CourseResponse:
    """Create a new course using AI generation.

    Returns 202 immediately with the draft course in a ``generating`` state;
    a durable worker builds the outline and lesson content out-of-request.
    Books arrive as references (bookIds); images arrive inline as base64
    data URLs that feed the LLM prompt and are never persisted.
    """
    prompt_text = request.prompt.strip()
    if not prompt_text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Prompt must not be empty")

    return await facade.create_course(
        {"prompt": prompt_text, "adaptive_enabled": request.adaptive_enabled},
        auth.user_id,
        book_ids=list(dict.fromkeys(request.book_ids)),
        image_data_urls=request.image_data_urls,
    )


@router.get("")
async def list_courses(
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    per_page: Annotated[int, Query(alias="perPage", ge=1, le=100, description="Items per page")] = 20,
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


@router.get("/{course_id}/attachments")
async def list_course_attachments(
    course_id: uuid.UUID,
    auth: CurrentAuth,
    svc: Annotated[CourseAttachmentsService, Depends(get_course_attachments_service)],
) -> list[CourseAttachmentRead]:
    """List books attached to a course."""
    return await svc.list_attachments(course_id, auth.user_id)


@router.post("/{course_id}/attachments")
async def attach_books_to_course(
    course_id: uuid.UUID,
    payload: CourseAttachmentBulkCreate,
    auth: CurrentAuth,
    svc: Annotated[CourseAttachmentsService, Depends(get_course_attachments_service)],
) -> list[CourseAttachmentRead]:
    """Attach books to a course idempotently; returns the full current list."""
    return await svc.attach_books(course_id, auth.user_id, payload.book_ids)


@router.delete("/{course_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def detach_book_from_course(
    course_id: uuid.UUID,
    attachment_id: uuid.UUID,
    auth: CurrentAuth,
    svc: Annotated[CourseAttachmentsService, Depends(get_course_attachments_service)],
) -> None:
    """Delete one attachment link; the book stays in the library."""
    await svc.detach(course_id, attachment_id, auth.user_id)


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
    )

    # Minimal analytics log
    logger.info(
        "CODE_EXECUTION",
        extra={
            "user_id": str(auth.user_id),
            "lesson_id": str(request.lesson_id) if request.lesson_id else None,
            "language": request.language,
            "status": response.status,
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
    data = await svc.start_process(
        command=request.command,
        user_id=str(auth.user_id),
        course_id=str(request.course_id) if request.course_id else None,
        workspace_id=request.workspace_id,
        cwd=request.cwd,
        env=request.env,
        user=request.user,
    )
    return RuntimeToolResponse(data=data)


@router.post("/runtime/process/output")
async def runtime_read_process_output(
    request: RuntimeProcessReadRequest,
    auth: CurrentAuth,
    svc: Annotated[CodeExecutionService, Depends(get_code_execution_service)],
) -> RuntimeToolResponse:
    """Read incremental output for a long-lived runtime process."""
    data = await svc.read_process_output(
        process_id=request.process_id,
        user_id=str(auth.user_id),
        course_id=str(request.course_id) if request.course_id else None,
        workspace_id=request.workspace_id,
    )
    return RuntimeToolResponse(data=data)


@router.post("/runtime/process/input")
async def runtime_send_process_input(
    request: RuntimeProcessInputRequest,
    auth: CurrentAuth,
    svc: Annotated[CodeExecutionService, Depends(get_code_execution_service)],
) -> RuntimeToolResponse:
    """Send stdin input to a long-lived runtime process."""
    data = await svc.send_process_input(
        process_id=request.process_id,
        input_text=request.input,
        user_id=str(auth.user_id),
        course_id=str(request.course_id) if request.course_id else None,
        workspace_id=request.workspace_id,
    )
    return RuntimeToolResponse(data=data)


@router.post("/runtime/process/stop")
async def runtime_stop_process(
    request: RuntimeProcessStopRequest,
    auth: CurrentAuth,
    svc: Annotated[CodeExecutionService, Depends(get_code_execution_service)],
) -> RuntimeToolResponse:
    """Stop a long-lived runtime process."""
    data = await svc.stop_process(
        process_id=request.process_id,
        user_id=str(auth.user_id),
        course_id=str(request.course_id) if request.course_id else None,
        workspace_id=request.workspace_id,
        wait_timeout_seconds=request.wait_timeout_seconds,
    )
    return RuntimeToolResponse(data=data)


@router.post("/runtime/list")
async def runtime_list_entries(
    request: RuntimeListRequest,
    auth: CurrentAuth,
    svc: Annotated[CodeExecutionService, Depends(get_code_execution_service)],
) -> RuntimeToolResponse:
    """List runtime filesystem entries for scoped lab/course sessions."""
    data = await svc.list_runtime_entries(
        path=request.path,
        depth=request.depth,
        user_id=str(auth.user_id),
        course_id=str(request.course_id) if request.course_id else None,
        workspace_id=request.workspace_id,
    )
    return RuntimeToolResponse(data=data)
