"""Course share links: mint, preview, and fork.

Lives on its own prefix rather than under ``/courses/{course_id}`` because that
path parameter is a UUID, so a literal segment there would fail validation.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.auth import CurrentAuth
from src.courses.schemas import CourseResponse, CourseShareCreate, CourseSharePreview, CourseShareResponse
from src.courses.services.course_query_service import CourseQueryService
from src.courses.services.course_share_service import CourseShareService


router = APIRouter(
    prefix="/api/v1/course-shares",
    tags=["course-shares"],
)


def get_course_share_service(auth: CurrentAuth) -> CourseShareService:
    """Get course share service instance."""
    return CourseShareService(auth.session)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_course_share(
    request: CourseShareCreate,
    auth: CurrentAuth,
    svc: Annotated[CourseShareService, Depends(get_course_share_service)],
) -> CourseShareResponse:
    """Mint a join link that lets another learner add a copy of an owned course."""
    return await svc.create_share(course_id=request.course_id, user_id=auth.user_id)


@router.get("/{token}")
async def get_course_share(
    token: str,
    svc: Annotated[CourseShareService, Depends(get_course_share_service)],
) -> CourseSharePreview:
    """Preview a shared course before adding it."""
    return await svc.get_preview(token)


@router.post("/{token}/fork", status_code=status.HTTP_201_CREATED)
async def fork_course_share(
    token: str,
    auth: CurrentAuth,
    svc: Annotated[CourseShareService, Depends(get_course_share_service)],
) -> CourseResponse:
    """Add a copy of the shared course to the caller's library."""
    course = await svc.fork(token=token, user_id=auth.user_id)
    return await CourseQueryService(auth.session).get_course(course.id, auth.user_id)
