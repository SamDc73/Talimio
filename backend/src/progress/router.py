"""Router for progress API."""

from fastapi import APIRouter, HTTPException, status

from src.core.exceptions import ResourceNotFoundError, ValidationError
from src.database.session import DbSession
from src.progress.schemas import (
    CourseProgressResponse,
    ErrorResponse,
    LessonStatusesResponse,
    LessonStatusResponse,
    StatusUpdate,
)
from src.progress.service import ProgressService


router = APIRouter(prefix="/api/v1/progress", tags=["progress"])


@router.put(
    "/lesson/{lesson_id}/status",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid status value"},
        404: {"model": ErrorResponse, "description": "Lesson not found"},
    },
)
async def update_lesson_status(
    lesson_id: str,
    data: StatusUpdate,
    session: DbSession,
) -> LessonStatusResponse:
    """Update lesson status.

    Args:
        lesson_id: Lesson ID
        data: Status update data
        session: Database session

    Returns
    -------
        Updated lesson status

    Raises
    ------
        HTTPException: If lesson not found or status is invalid
    """
    service = ProgressService(session)
    try:
        progress = await service.update_lesson_status(lesson_id, data)
        return LessonStatusResponse(
            lesson_id=progress.lesson_id,
            status=progress.status,
            updated_at=progress.updated_at,
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get(
    "/course/{course_id}",
    responses={
        404: {"model": ErrorResponse, "description": "Course not found"},
    },
)
async def get_course_progress(
    course_id: str,
    session: DbSession,
) -> CourseProgressResponse:
    """Get course progress.

    Args:
        course_id: Course ID
        session: Database session

    Returns
    -------
        Course progress

    Raises
    ------
        HTTPException: If course not found
    """
    service = ProgressService(session)
    try:
        total_lessons, completed_lessons, progress_percentage = await service.get_course_progress(course_id)
        return CourseProgressResponse(
            course_id=course_id,
            total_lessons=total_lessons,
            completed_lessons=completed_lessons,
            progress_percentage=progress_percentage,
        )
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get(
    "/course/{course_id}/lessons",
    responses={
        404: {"model": ErrorResponse, "description": "Course not found"},
    },
)
async def get_lesson_statuses(
    course_id: str,
    session: DbSession,
) -> LessonStatusesResponse:
    """Get lesson statuses for a course.

    Args:
        course_id: Course ID
        session: Database session

    Returns
    -------
        Lesson statuses

    Raises
    ------
        HTTPException: If course not found
    """
    service = ProgressService(session)
    try:
        lesson_statuses = await service.get_lesson_statuses(course_id)
        return LessonStatusesResponse(lessons=lesson_statuses)
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
