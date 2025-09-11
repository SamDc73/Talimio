"""Progress tracking API endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from src.auth import CurrentAuth
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
    response: Response,
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

    # Convert to ProgressData objects
    progress_map = {
        content_id: ProgressData(progress_percentage=data["progress_percentage"], metadata=data["metadata"])
        for content_id, data in progress_data.items()
    }

    return BatchProgressResponse(progress=progress_map)


@router.get("/{content_id}")
async def get_single_progress(
    content_id: UUID,
    auth: CurrentAuth,
) -> ProgressResponse:
    """Get progress for a single content item."""
    service = ProgressService(auth.session)
    progress = await service.get_single_progress(auth.user_id, content_id)

    if not progress:
        # Check if content exists and get its type
        content_type = await service.get_content_type(content_id, auth.user_id)
        if not content_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Content {content_id} not found or access denied",
            )

        # Return virtual progress (no DB write)
        return ProgressResponse(
            id=UUID("00000000-0000-0000-0000-000000000000"),
            content_id=content_id,
            content_type=content_type,  # Use actual type, not default "book"
            progress_percentage=0.0,
            metadata={},
            created_at=None,
            updated_at=None,
        )

    return progress


@router.put("/{content_id}")
# @progress_rate_limit  # TODO: Re-enable rate limiting when needed
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

    logger.info(
        f"Updated progress for user {auth.user_id}, content {content_id}: {progress.progress_percentage}%"
    )

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
