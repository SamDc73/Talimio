"""Progress tracking API endpoints."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import UserId
from src.database.session import get_db_session
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
    user_id: UserId,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BatchProgressResponse:
    """Get progress for multiple content items in one request."""
    if len(request.content_ids) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Batch size exceeds maximum of {MAX_BATCH_SIZE}",
        )

    service = ProgressService(session)
    progress_data = await service.get_batch_progress(user_id, request.content_ids)

    # Convert to ProgressData objects
    progress_map = {
        content_id: ProgressData(progress_percentage=data["progress_percentage"], metadata=data["metadata"])
        for content_id, data in progress_data.items()
    }

    # Add cache control header (30 seconds)
    response.headers["Cache-Control"] = "private, max-age=30"

    return BatchProgressResponse(progress=progress_map)


@router.get("/{content_id}")
async def get_single_progress(
    content_id: UUID,
    user_id: UserId,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProgressResponse:
    """Get progress for a single content item."""
    service = ProgressService(session)
    progress = await service.get_single_progress(user_id, content_id)

    if not progress:
        # Return default progress if none exists
        return ProgressResponse(
            id=UUID("00000000-0000-0000-0000-000000000000"),
            user_id=user_id,
            content_id=content_id,
            content_type="book",  # Default, will be updated on first save
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
    user_id: UserId,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProgressResponse:
    """Update progress for a content item."""
    service = ProgressService(session)

    # Determine content type
    content_type = await service.get_content_type(content_id)
    if not content_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content {content_id} not found",
        )

    # Update progress
    result = await service.update_progress(user_id, content_id, content_type, progress)

    logger.info(f"Updated progress for user {user_id}, content {content_id}: {progress.progress_percentage}%")

    return result


@router.delete("/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_progress(
    content_id: UUID,
    user_id: UserId,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Delete progress for a content item."""
    service = ProgressService(session)
    deleted = await service.delete_progress(user_id, content_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Progress for content {content_id} not found",
        )

    logger.info(f"Deleted progress for user {user_id}, content {content_id}")
