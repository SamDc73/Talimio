"""Unified courses API router.

This router provides the new unified course API structure that replaces
the separated /roadmaps, /lessons, and /nodes endpoints.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import EffectiveUserId
from src.courses.schemas import (
    CourseCreate,
    CourseListResponse,
    CourseProgressResponse,
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
    session: AsyncSession = Depends(get_db_session)
) -> CourseService:
    """Get course service instance."""
    # User ID will be passed directly to methods that need it
    return CourseService(session)


# Course operations
@router.post("/")
async def create_course(
    request: CourseCreate,
    course_service: Annotated[CourseService, Depends(get_course_service)],
    user_id: EffectiveUserId,
) -> CourseResponse:
    """Create a new course using AI generation."""
    return await course_service.create_course(request, user_id)


@router.get("/")
async def list_courses(
    course_service: Annotated[CourseService, Depends(get_course_service)],
    user_id: EffectiveUserId,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    per_page: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    search: Annotated[str | None, Query(description="Search query")] = None,
) -> CourseListResponse:
    """List courses with pagination and optional search."""
    courses, total = await course_service.list_courses(page, per_page, search, user_id)

    return CourseListResponse(courses=courses, total=total, page=page, per_page=per_page)


@router.get("/{course_id}")
async def get_course(
    course_id: UUID,
    course_service: Annotated[CourseService, Depends(get_course_service)],
    user_id: EffectiveUserId,
) -> CourseResponse:
    """Get a specific course by ID."""
    return await course_service.get_course(course_id, user_id)


@router.patch("/{course_id}")
async def update_course(
    course_id: UUID,
    request: CourseUpdate,
    course_service: Annotated[CourseService, Depends(get_course_service)],
    user_id: EffectiveUserId,
) -> CourseResponse:
    """Update a course."""
    return await course_service.update_course(course_id, request, user_id)


# Full lesson access (with module_id for web app compatibility)
@router.get("/{course_id}/modules/{module_id}/lessons/{lesson_id}")
async def get_lesson_full_path(
    course_id: UUID,
    module_id: UUID,
    lesson_id: UUID,
    course_service: Annotated[CourseService, Depends(get_course_service)],
    user_id: EffectiveUserId,
    generate: Annotated[bool, Query(description="Auto-generate if lesson doesn't exist")] = False,
) -> LessonResponse:
    """Get a specific lesson by course, module, and lesson ID (full hierarchical route)."""
    # Delegate to the existing lesson service - module_id is just for routing
    return await course_service.get_lesson_simplified(course_id, lesson_id, generate, user_id)


# Simplified lesson access (without module_id requirement)
@router.get("/{course_id}/lessons/{lesson_id}")
async def get_lesson_simplified(
    course_id: UUID,
    lesson_id: UUID,
    course_service: Annotated[CourseService, Depends(get_course_service)],
    user_id: EffectiveUserId,
    generate: Annotated[bool, Query(description="Auto-generate if lesson doesn't exist")] = False,
) -> LessonResponse:
    """Get a specific lesson by course and lesson ID (simplified route without module_id)."""
    return await course_service.get_lesson_simplified(course_id, lesson_id, generate, user_id)


# Progress tracking operations
@router.get("/{course_id}/progress")
async def get_course_progress(
    course_id: UUID,
    course_service: Annotated[CourseService, Depends(get_course_service)],
    user_id: EffectiveUserId,
) -> CourseProgressResponse:
    """Get overall progress for a course."""
    return await course_service.get_course_progress(course_id, user_id)


@router.patch("/{course_id}/modules/{module_id}/lessons/{lesson_id}/status")
async def update_lesson_status(
    course_id: UUID,
    module_id: UUID,
    lesson_id: UUID,
    request: LessonStatusUpdate,
    course_service: Annotated[CourseService, Depends(get_course_service)],
    user_id: EffectiveUserId,
) -> LessonStatusResponse:
    """Update the status of a specific lesson."""
    return await course_service.update_lesson_status(course_id, module_id, lesson_id, request, user_id)


# Simplified lesson status endpoint (without module_id requirement)
@router.patch("/{course_id}/lessons/{lesson_id}/status")
async def update_lesson_status_simplified(
    course_id: UUID,
    lesson_id: UUID,
    request: LessonStatusUpdate,
    course_service: Annotated[CourseService, Depends(get_course_service)],
    user_id: EffectiveUserId,
) -> LessonStatusResponse:
    """Update the status of a specific lesson (simplified route without module_id)."""
    # Pass course_id as module_id for compatibility with existing service
    return await course_service.update_lesson_status(course_id, course_id, lesson_id, request, user_id)


@router.get("/{course_id}/modules/{module_id}/lessons/{lesson_id}/status")
async def get_lesson_status(
    course_id: UUID,
    module_id: UUID,
    lesson_id: UUID,
    course_service: Annotated[CourseService, Depends(get_course_service)],
    user_id: EffectiveUserId,
) -> LessonStatusResponse:
    """Get the status of a specific lesson."""
    return await course_service.get_lesson_status(course_id, module_id, lesson_id, user_id)


# Simplified lesson status endpoint (without module_id requirement)
@router.get("/{course_id}/lessons/{lesson_id}/status")
async def get_lesson_status_simplified(
    course_id: UUID,
    lesson_id: UUID,
    course_service: Annotated[CourseService, Depends(get_course_service)],
    user_id: EffectiveUserId,
) -> LessonStatusResponse:
    """Get the status of a specific lesson (simplified route without module_id)."""
    # Pass course_id as module_id for compatibility with existing service
    return await course_service.get_lesson_status(course_id, course_id, lesson_id, user_id)


# Get all lesson statuses for a course
@router.get("/{course_id}/lessons/statuses")
async def get_all_lesson_statuses(
    course_id: UUID,
    course_service: Annotated[CourseService, Depends(get_course_service)],
    user_id: EffectiveUserId,
) -> dict[str, str]:
    """Get all lesson statuses for a course."""
    return await course_service.get_all_lesson_statuses(course_id, user_id)
