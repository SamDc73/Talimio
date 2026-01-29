"""Progress tracking API endpoints."""

import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Response, status

from src.auth import CurrentAuth
from src.courses.services.course_progress_service import CourseProgressService
from src.middleware.security import limiter

from .models import (
    BatchProgressRequest,
    BatchProgressResponse,
    ProgressData,
    ProgressResponse,
    ProgressUpdate,
)
from .service import ProgressService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/progress", tags=["progress"])

MAX_BATCH_SIZE = 100  # Prevent unbounded requests

# Create a specific rate limiter for progress updates
# 10 updates per minute per user
progress_rate_limit = limiter.limit("10/minute")


@router.post("/batch")
async def get_batch_progress(
    request: BatchProgressRequest,
    _response: Response,
    auth: CurrentAuth,
) -> BatchProgressResponse:
    """Get progress for multiple content items in one request."""
    if len(request.content_ids) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Batch size exceeds maximum of {MAX_BATCH_SIZE}",
        )

    service = ProgressService(auth.session)
    progress_data = await service.get_batch_progress(auth.user_id, request.content_ids)

    # Start with DB results
    progress_map: dict[str, ProgressData] = {
        content_id: ProgressData(progressPercentage=data["progress_percentage"], metadata=data["metadata"])
        for content_id, data in progress_data.items()
    }

    # For courses, override with canonical adaptive calculation
    cps = CourseProgressService(auth.session)
    for cid in request.content_ids:
        ctype = await service.get_content_type(cid, auth.user_id)
        if ctype == "course":
            computed = await cps.get_progress(cid, auth.user_id)
            # Drop completion_percentage from metadata
            meta = {k: v for k, v in computed.items() if k != "completion_percentage"}
            progress_map[str(cid)] = ProgressData(
                progressPercentage=computed.get("completion_percentage", 0.0),
                metadata=meta,
            )

    return BatchProgressResponse(progress=progress_map)


@router.get("/{content_id}")
async def get_single_progress(
    content_id: UUID,
    auth: CurrentAuth,
) -> ProgressResponse:
    """Get progress for a single content item."""
    service = ProgressService(auth.session)

    # Determine content type first to unify behavior
    content_type = await service.get_content_type(content_id, auth.user_id)
    if not content_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content {content_id} not found or access denied",
        )

    # For courses, compute canonical adaptive progress from concept mastery
    if content_type == "course":
        # Fetch row only to reuse timestamps if present
        row = await service.get_single_progress(auth.user_id, content_id)
        computed = await CourseProgressService(auth.session).get_progress(content_id, auth.user_id)
        metadata = {k: v for k, v in computed.items() if k != "completion_percentage"}
        return ProgressResponse(
            id=row.id if row else uuid4(),
            content_id=content_id,
            content_type="course",
            progress_percentage=computed.get("completion_percentage", 0.0),
            metadata=metadata,
            created_at=row.created_at if row else None,
            updated_at=row.updated_at if row else None,
        )

    # Non-course: return stored row or virtual default
    progress = await service.get_single_progress(auth.user_id, content_id)
    if not progress:
        return ProgressResponse(
            id=uuid4(),
            content_id=content_id,
            content_type=content_type,
            progress_percentage=0.0,
            metadata={},
            created_at=None,
            updated_at=None,
        )
    return progress


@router.put("/{content_id}")
async def update_progress(
    content_id: UUID,
    progress: ProgressUpdate,
    auth: CurrentAuth,
) -> ProgressResponse:
    """Update progress for a content item."""
    service = ProgressService(auth.session)

    # Determine content type - now validates ownership
    content_type = await service.get_content_type(content_id, auth.user_id)
    if not content_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content {content_id} not found or access denied",
        )

    # Update progress
    result = await service.update_progress(auth.user_id, content_id, content_type, progress)

    logger.info(f"Updated progress for user {auth.user_id}, content {content_id}: {progress.progress_percentage}%")

    return result


@router.delete("/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_progress(
    content_id: UUID,
    auth: CurrentAuth,
) -> None:
    """Delete progress for a content item."""
    service = ProgressService(auth.session)
    deleted = await service.delete_progress(auth.user_id, content_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Progress for content {content_id} not found",
        )

    logger.info(f"Deleted progress for user {auth.user_id}, content {content_id}")
