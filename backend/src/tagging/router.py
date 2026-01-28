"""API endpoints for tagging operations."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

# AI imports removed - using facades instead
from src.auth import CurrentAuth
from src.database.session import get_db_session

from .schemas import (
    ContentTagsUpdate,
    TaggingResponse,
    TagSchema,
)
from .service import TaggingService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tags", tags=["tags"])


async def get_tagging_service(
    session: AsyncSession = Depends(get_db_session),
) -> TaggingService:
    """Get tagging service instance."""
    # TaggingService no longer needs model_manager
    return TaggingService(session)


# Content type validation dependency
VALID_CONTENT_TYPES = ["book", "video", "course"]


def validate_content_type(content_type: str) -> str:
    """Validate content type parameter.

    Args:
        content_type: Type of content to validate

    Returns
    -------
        The validated content type

    Raises
    ------
        HTTPException: If content type is invalid
    """
    if content_type not in VALID_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid content type: {content_type}. Must be one of: {', '.join(VALID_CONTENT_TYPES)}",
        )
    return content_type


@router.get("/tags")
async def list_tags(
    _auth: CurrentAuth,
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


@router.get("/{content_type}/{content_id}/tags")
async def get_content_tags(
    content_type: str,
    content_id: UUID,
    auth: CurrentAuth,
    service: Annotated[TaggingService, Depends(get_tagging_service)],
) -> list[TagSchema]:
    """Get all tags for a specific content item.

    Args:
        content_type: Type of content (book, video, course)
        content_id: UUID of the content
        user_id: Current authenticated user
        service: Tagging service instance

    Returns
    -------
        List of tags for the content
    """
    # Validate content type
    content_type = validate_content_type(content_type)

    tags = await service.get_content_tags(content_id, content_type, auth.user_id)
    return [TagSchema.model_validate(tag) for tag in tags]


@router.put("/{content_type}/{content_id}/tags")
async def update_content_tags(
    content_type: str,
    content_id: UUID,
    request: ContentTagsUpdate,
    auth: CurrentAuth,
    service: Annotated[TaggingService, Depends(get_tagging_service)],
) -> TaggingResponse:
    """Update tags for a content item (manual tagging).

    Args:
        content_type: Type of content (book, video, course)
        content_id: UUID of the content
        request: Update request with new tags
        user_id: Current authenticated user
        service: Tagging service instance

    Returns
    -------
        TaggingResponse with updated tags
    """
    # Validate content type
    content_type = validate_content_type(content_type)

    try:
        await service.update_manual_tags(
            content_id=content_id,
            content_type=content_type,
            user_id=auth.user_id,
            tag_names=request.tags,
        )

        # Also update content's tags field
        from .service import update_content_tags_json

        await update_content_tags_json(
            service.session,
            content_id,
            content_type,
            request.tags,
        )

        return TaggingResponse(
            content_id=content_id,
            content_type=content_type,
            tags=request.tags,
            auto_generated=False,
            success=True,
        )

    except Exception as e:
        logger.exception(f"Error updating tags for {content_type} {content_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update tags: {e!s}",
        ) from e

