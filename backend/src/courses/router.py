"""Unified courses API router.

This router provides the new unified course API structure that replaces
the separated /roadmaps, /lessons, and /nodes endpoints.

NOTE: This router has been fully migrated to use CoursesFacade.
CourseOrchestratorService has been completely removed and replaced with
CoursesFacade for all endpoints including lesson-specific operations.
"""

import logging
import os
import time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import CurrentAuth
from src.courses.facade import CoursesFacade
from src.courses.schemas import (
    CodeExecuteRequest,
    CodeExecuteResponse,
    CourseCreate,
    CourseListResponse,
    CourseResponse,
    CourseUpdate,
    LessonResponse,
    MDXValidateRequest,
    MDXValidateResponse,
)
from src.courses.services.code_execution_service import CodeExecutionError, CodeExecutionService
from src.courses.services.lesson_service import LessonService
from src.courses.services.mdx_service import mdx_service
from src.database.session import get_db_session


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


# Course operations
@router.post("/")
async def create_course(
    request: CourseCreate,
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
) -> CourseResponse:
    """Create a new course using AI generation."""
    result = await facade.create_course(request.model_dump(), auth.user_id)
    if not result.get("success"):
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=result.get("error", "Failed to create course"))

    return result["course"]


@router.get("/")
async def list_courses(
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    per_page: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    search: Annotated[str | None, Query(description="Search query")] = None,
) -> CourseListResponse:
    """List courses with pagination and optional search."""
    result = await facade.get_user_courses(auth.user_id, include_progress=True)

    if not result.get("success"):
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=result.get("error", "Failed to get courses"))

    courses = result["courses"]

    # Apply search filter if provided
    if search:
        search_result = await facade.search_courses(search, auth.user_id, {"limit": per_page})
        if search_result.get("success"):
            courses = search_result["results"]

    # Simple pagination (could be improved)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_courses = courses[start:end]
    total = len(courses)

    return CourseListResponse(courses=paginated_courses, total=total, page=page, per_page=per_page)


@router.get("/{course_id}")
async def get_course(
    course_id: UUID,
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
) -> CourseResponse:
    """Get a specific course by ID."""
    result = await facade.get_course_with_progress(course_id, auth.user_id)

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


@router.delete("/{course_id}")
async def delete_course(
    course_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    auth: CurrentAuth,
) -> None:
    """Delete a course."""
    try:
        facade = CoursesFacade()
        await facade.delete_course(db=db, course_id=course_id, user_id=auth.user_id)
        await db.commit()
    except ValueError as e:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        from fastapi import HTTPException

        raise HTTPException(status_code=500, detail=str(e)) from e


# Full lesson access (with module_id for web app compatibility)
@router.get("/{course_id}/modules/{module_id}/lessons/{lesson_id}")
async def get_lesson_full_path(
    course_id: UUID,
    module_id: UUID,
    lesson_id: UUID,
    auth: CurrentAuth,
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
    generate: Annotated[bool, Query(description="Auto-generate if lesson doesn't exist")] = False,
) -> LessonResponse:
    """Get a specific lesson by course, module, and lesson ID (full hierarchical route)."""
    # Delegate to the existing lesson service - module_id is just for routing (unused)
    _ = module_id  # Explicitly ignore unused parameter
    return await facade.get_lesson_simplified(course_id, lesson_id, generate, auth.user_id)


# Main lesson access endpoint with single query and user isolation
@router.get("/{course_id}/lessons/{lesson_id}")
async def get_lesson(
    course_id: UUID,
    lesson_id: UUID,
    lesson_service: Annotated[LessonService, Depends(get_lesson_service)],
    generate: Annotated[bool, Query(description="Auto-generate if lesson doesn't exist")] = False,
) -> LessonResponse:
    """Get a specific lesson by course and lesson ID."""
    return await lesson_service.get_lesson(course_id, lesson_id, generate)


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

# very small in-memory per-user rate limiter (no over-engineering)
_rate_state: dict[str, tuple[float, int]] = {}


def _check_rate_limit(user_id: UUID) -> None:
    limit = int(os.getenv("CODE_EXEC_RATE_LIMIT_PER_USER", "10"))
    window = int(os.getenv("CODE_EXEC_RATE_LIMIT_WINDOW", "60"))
    now = time.time()
    key = str(user_id)
    start, count = _rate_state.get(key, (now, 0))
    if now - start > window:
        _rate_state[key] = (now, 1)
        return
    if count + 1 > limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")
    _rate_state[key] = (start, count + 1)


@router.post("/code/execute")
async def execute_code(
    request: CodeExecuteRequest,
    auth: CurrentAuth,
    svc: Annotated[CodeExecutionService, Depends(get_code_execution_service)],
    facade: Annotated[CoursesFacade, Depends(get_courses_facade)],
) -> CodeExecuteResponse:
    """Execute a single code snippet via E2B sandbox.

    Auth is required; rate limited per user; minimal logging/analytics.
    Uses course-scoped sandboxes with setup_commands for fast execution.
    """
    _check_rate_limit(auth.user_id)

    # Fetch setup_commands from course if course_id provided
    setup_commands: list[str] = []
    if request.course_id:
        try:
            result = await facade.get_course_with_progress(request.course_id, auth.user_id)
            if result.get("success") and "course" in result:
                course = result["course"]
                setup_commands = course.setup_commands or []
        except Exception:
            logger.debug("Could not fetch course setup_commands for course_id=%s", request.course_id)

    try:
        result = await svc.execute(
            source_code=request.code,
            language=request.language,
            stdin=request.stdin,
            user_id=str(auth.user_id),
            course_id=str(request.course_id) if request.course_id else None,
            lesson_id=str(request.lesson_id) if request.lesson_id else None,
            setup_commands=setup_commands,
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
