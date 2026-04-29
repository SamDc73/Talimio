"""API endpoints for tagging operations."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from src.auth import CurrentAuth

from .schemas import (
    ContentTagsUpdate,
    TaggingResponse,
    TagSchema,
)
from .service import TaggingService


router = APIRouter(prefix="/api/v1/tags", tags=["tags"])


def get_tagging_service(auth: CurrentAuth) -> TaggingService:
    """Get tagging service instance."""
    return TaggingService(auth.session)


@router.get("")
async def list_tags(
    service: Annotated[TaggingService, Depends(get_tagging_service)],
    category: str | None = None,
    limit: int = 100,
) -> list[TagSchema]:
    """List all available tags.

    Args:
        category: Optional category filter
        limit: Maximum number of tags to return
        service: Tagging service instance

    Returns
    -------
        List of tags
    """
    tags = await service.get_all_tags(category=category, limit=limit)
    return [TagSchema.model_validate(tag) for tag in tags]


@router.get("/{content_type}/{content_id}")
async def get_content_tags(
    content_type: str,
    content_id: uuid.UUID,
    auth: CurrentAuth,
    service: Annotated[TaggingService, Depends(get_tagging_service)],
) -> list[TagSchema]:
    """Get all tags for a specific content item.

    Args:
        content_type: Type of content (book, video, course)
        content_id: uuid.UUID of the content
        user_id: Current authenticated user
        service: Tagging service instance

    Returns
    -------
        List of tags for the content
    """
    content_type = service.validate_content_type(content_type)
    tags = await service.get_content_tags(content_id, content_type, auth.user_id)
    return [TagSchema.model_validate(tag) for tag in tags]


@router.put("/{content_type}/{content_id}")
async def update_content_tags(
    content_type: str,
    content_id: uuid.UUID,
    request: ContentTagsUpdate,
    auth: CurrentAuth,
    service: Annotated[TaggingService, Depends(get_tagging_service)],
) -> TaggingResponse:
    """Update tags for a content item (manual tagging).

    Args:
        content_type: Type of content (book, video, course)
        content_id: uuid.UUID of the content
        request: Update request with new tags
        user_id: Current authenticated user
        service: Tagging service instance

    Returns
    -------
        TaggingResponse with updated tags
    """
    return await service.update_content_tags(
        content_id=content_id,
        content_type=content_type,
        user_id=auth.user_id,
        tag_names=request.tags,
    )
