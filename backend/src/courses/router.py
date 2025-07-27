"""Unified courses API router.

This router provides the new unified course API structure that replaces
the separated /roadmaps, /lessons, and /nodes endpoints.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import UserId
from src.courses.schemas import (
    CourseCreate,
    CourseListResponse,
    CourseResponse,
    CourseUpdate,
    LessonResponse,
    LessonStatusResponse,
    LessonStatusUpdate,
)
from src.courses.services.course_service import CourseService
from src.database.session import get_db_session


router = APIRouter(
    prefix="/api/v1/courses",
    tags=["courses"],
    responses={404: {"description": "Not found"}},
)


def get_course_service(
    user_id: UserId,
    session: AsyncSession = Depends(get_db_session),
) -> CourseService:
    """Get course service instance with simple user_id injection."""
    return CourseService(session, user_id)


async def _find_module_id_for_lesson(session: AsyncSession, course_id: UUID, lesson_id: UUID) -> UUID:
    """Find the module_id (parent_id) for a given lesson.

    Args:
        session: Database session
        course_id: Course ID
        lesson_id: Lesson ID

    Returns
    -------
        The module ID (parent_id) of the lesson

    Raises
    ------
        HTTPException: If lesson not found
    """
    from src.courses.models import Node

    # Find the lesson and get its parent_id (module_id)
    lesson_query = select(Node).where(
        Node.id == lesson_id,
        Node.roadmap_id == course_id
    )

    result = await session.execute(lesson_query)
    lesson = result.scalar_one_or_none()

    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lesson {lesson_id} not found in course {course_id}"
        )

    # Return the parent_id as module_id, or use lesson_id if no parent (for top-level lessons)
    return lesson.parent_id if lesson.parent_id else lesson.id


# Course operations
@router.post("/")
async def create_course(
    request: CourseCreate,
    course_service: Annotated[CourseService, Depends(get_course_service)],  #Simple dependency injection
) -> CourseResponse:
    """Create a new course using AI generation."""
    return await course_service.create_course(request)


@router.get("/")
async def list_courses(
    course_service: Annotated[CourseService, Depends(get_course_service)],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    per_page: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    search: Annotated[str | None, Query(description="Search query")] = None,
) -> CourseListResponse:
    """List courses with pagination and optional search."""
    courses, total = await course_service.list_courses(page, per_page, search)

    return CourseListResponse(courses=courses, total=total, page=page, per_page=per_page)


@router.get("/{course_id}")
async def get_course(
    course_id: UUID,
    course_service: Annotated[CourseService, Depends(get_course_service)],
) -> CourseResponse:
    """Get a specific course by ID."""
    return await course_service.get_course(course_id)


@router.patch("/{course_id}")
async def update_course(
    course_id: UUID,
    request: CourseUpdate,
    course_service: Annotated[CourseService, Depends(get_course_service)],
) -> CourseResponse:
    """Update a course."""
    return await course_service.update_course(course_id, request)


@router.delete("/{course_id}")
async def delete_course(
    course_id: UUID,
    course_service: Annotated[CourseService, Depends(get_course_service)],
) -> None:
    """Delete a course."""
    await course_service.delete_course(course_id)


# Full lesson access (with module_id for web app compatibility)
@router.get("/{course_id}/modules/{module_id}/lessons/{lesson_id}")
async def get_lesson_full_path(
    course_id: UUID,
    module_id: UUID,
    lesson_id: UUID,
    course_service: Annotated[CourseService, Depends(get_course_service)],
    generate: Annotated[bool, Query(description="Auto-generate if lesson doesn't exist")] = False,
) -> LessonResponse:
    """Get a specific lesson by course, module, and lesson ID (full hierarchical route)."""
    # Delegate to the existing lesson service - module_id is just for routing (unused)
    _ = module_id  # Explicitly ignore unused parameter
    return await course_service.get_lesson_simplified(course_id, lesson_id, generate)


# Get all lesson statuses for a course (must be before {lesson_id} route)
@router.get("/{course_id}/lessons/statuses")
async def get_all_lesson_statuses(
    course_id: UUID,
    course_service: Annotated[CourseService, Depends(get_course_service)],
) -> dict[str, str]:
    """Get all lesson statuses for a course."""
    return await course_service.get_all_lesson_statuses(course_id)


# Simplified lesson access (without module_id requirement)
@router.get("/{course_id}/lessons/{lesson_id}")
async def get_lesson_simplified(
    course_id: UUID,
    lesson_id: UUID,
    course_service: Annotated[CourseService, Depends(get_course_service)],
    generate: Annotated[bool, Query(description="Auto-generate if lesson doesn't exist")] = False,
) -> LessonResponse:
    """Get a specific lesson by course and lesson ID (simplified route without module_id)."""
    return await course_service.get_lesson_simplified(course_id, lesson_id, generate)


# Progress tracking operations removed - use unified /api/v1/content endpoint instead
# Adding temporary debug endpoint
@router.get("/{course_id}/progress")
async def get_course_progress_debug(
    course_id: UUID,
    user_id: UserId,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Debug endpoint to check course progress calculation."""
    from src.courses.services.course_progress_service import CourseProgressService

    progress_service = CourseProgressService(session, user_id)
    stats = await progress_service.get_lesson_completion_stats(course_id, user_id)

    return {
        "course_id": str(course_id),
        "total_lessons": stats["total_lessons"],
        "completed_lessons": stats["completed_lessons"],
        "in_progress_lessons": stats["in_progress_lessons"],
        "completion_percentage": float(stats["completion_percentage"]),
    }


@router.patch("/{course_id}/modules/{module_id}/lessons/{lesson_id}/status")
async def update_lesson_status(
    course_id: UUID,
    module_id: UUID,
    lesson_id: UUID,
    request: LessonStatusUpdate,
    course_service: Annotated[CourseService, Depends(get_course_service)],
) -> LessonStatusResponse:
    """Update the status of a specific lesson."""
    return await course_service.update_lesson_status(course_id, module_id, lesson_id, request)


# Simplified lesson status endpoint (without module_id requirement)
@router.patch("/{course_id}/lessons/{lesson_id}/status")
async def update_lesson_status_simplified(
    course_id: UUID,
    lesson_id: UUID,
    request: LessonStatusUpdate,
    course_service: Annotated[CourseService, Depends(get_course_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LessonStatusResponse:
    """Update the status of a specific lesson (simplified route without module_id)."""
    # Find the actual module_id (parent_id) for this lesson
    module_id = await _find_module_id_for_lesson(session, course_id, lesson_id)
    return await course_service.update_lesson_status(course_id, module_id, lesson_id, request)


@router.get("/{course_id}/modules/{module_id}/lessons/{lesson_id}/status")
async def get_lesson_status(
    course_id: UUID,
    module_id: UUID,
    lesson_id: UUID,
    course_service: Annotated[CourseService, Depends(get_course_service)],
) -> LessonStatusResponse:
    """Get the status of a specific lesson."""
    return await course_service.get_lesson_status(course_id, module_id, lesson_id)


# Simplified lesson status endpoint (without module_id requirement)
@router.get("/{course_id}/lessons/{lesson_id}/status")
async def get_lesson_status_simplified(
    course_id: UUID,
    lesson_id: UUID,
    course_service: Annotated[CourseService, Depends(get_course_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LessonStatusResponse:
    """Get the status of a specific lesson (simplified route without module_id)."""
    # Find the actual module_id (parent_id) for this lesson
    module_id = await _find_module_id_for_lesson(session, course_id, lesson_id)
    return await course_service.get_lesson_status(course_id, module_id, lesson_id)


