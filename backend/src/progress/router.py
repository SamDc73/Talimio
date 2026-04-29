"""Progress tracking API endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from src.auth import CurrentAuth

from .models import (
    BatchProgressRequest,
    BatchProgressResponse,
    ProgressResponse,
    ProgressUpdate,
)
from .service import ProgressService


router = APIRouter(prefix="/api/v1/progress", tags=["progress"])

MAX_BATCH_SIZE = 100  # Prevent unbounded requests


def get_progress_service(auth: CurrentAuth) -> ProgressService:
    """Provide request-scoped progress service."""
    return ProgressService(auth.session)


@router.post("/batch")
async def get_batch_progress(
    request: BatchProgressRequest,
    _response: Response,
    auth: CurrentAuth,
    service: Annotated[ProgressService, Depends(get_progress_service)],
) -> BatchProgressResponse:
    """Get progress for multiple content items in one request."""
    if len(request.content_ids) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Batch size exceeds maximum of {MAX_BATCH_SIZE}",
        )

    return await service.get_batch_progress_response(auth.user_id, request.content_ids)


@router.get("/{content_id}")
async def get_single_progress(
    content_id: uuid.UUID,
    auth: CurrentAuth,
    service: Annotated[ProgressService, Depends(get_progress_service)],
) -> ProgressResponse:
    """Get progress for a single content item."""
    return await service.get_progress_response(auth.user_id, content_id)


@router.put("/{content_id}")
async def update_progress(
    content_id: uuid.UUID,
    progress: ProgressUpdate,
    auth: CurrentAuth,
    service: Annotated[ProgressService, Depends(get_progress_service)],
) -> ProgressResponse:
    """Update progress for a content item."""
    content_type = await service.require_content_type(content_id, auth.user_id)
    return await service.update_progress(auth.user_id, content_id, content_type, progress)


@router.delete("/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_progress(
    content_id: uuid.UUID,
    auth: CurrentAuth,
    service: Annotated[ProgressService, Depends(get_progress_service)],
) -> None:
    """Delete progress for a content item."""
    await service.delete_progress(auth.user_id, content_id)
