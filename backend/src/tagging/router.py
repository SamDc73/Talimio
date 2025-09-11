"""API endpoints for tagging operations."""

import logging
from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

# AI imports removed - using facades instead
from src.auth import CurrentAuth
from src.database.session import get_db_session

from .schemas import (
    BatchTaggingRequest,
    BatchTaggingResponse,
    ContentTagsUpdate,
    TaggingResponse,
    TagSchema,
    TagSuggestionRequest,
)
from .service import TaggingService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tags", tags=["tags"])


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


# Content processor mapping
async def get_content_processor(content_type: str) -> Callable:
    """Get the appropriate content processor for the given type.

    Args:
        content_type: Type of content to process

    Returns
    -------
        The processor function for the content type
    """
    processors = {
        "book": ("book_processor", "process_book_for_tagging"),
        "video": ("video_processor", "process_video_for_tagging"),
        "course": ("course_processor", "process_course_for_tagging"),
    }

    module_name, func_name = processors[content_type]
    module = __import__(f"src.tagging.processors.{module_name}", fromlist=[func_name])
    return getattr(module, func_name)


@router.post("/process/{content_type}/{content_id}")
async def tag_content(
    content_type: str,
    content_id: UUID,
    background_tasks: BackgroundTasks,
    auth: CurrentAuth,
    service: Annotated[TaggingService, Depends(get_tagging_service)],
) -> TaggingResponse:
    """Generate and store tags for a specific content item.

    Args:
        content_type: Type of content (book, video, course)
        content_id: UUID of the content
        background_tasks: FastAPI background tasks
        user_id: Current authenticated user
        service: Tagging service instance

    Returns
    -------
        TaggingResponse with generated tags
    """
    # Validate content type
    content_type = validate_content_type(content_type)

    try:
        # Get the appropriate processor dynamically
        process_content = await get_content_processor(content_type)

        # Process content to extract data for tagging
        # Convert content_id to string for book and course processors
        processor_id = str(content_id) if content_type in ["book", "course"] else content_id
        content_data = await process_content(processor_id, service.session)

        if not content_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{content_type.capitalize()} {content_id} not found",
            )

        # Generate and store tags
        tags = await service.tag_content(
            content_id=content_id,
            content_type=content_type,
            user_id=auth.user_id,
            title=content_data["title"],
            content_preview=content_data["content_preview"],
        )

        # Update content's tags field in background
        from .service import update_content_tags_json

        background_tasks.add_task(
            update_content_tags_json,
            service.session,
            content_id,
            content_type,
            tags,
        )

        return TaggingResponse(
            content_id=content_id,
            content_type=content_type,
            tags=tags,
            auto_generated=True,
            success=True,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error tagging {content_type} {content_id}: {e}")
        return TaggingResponse(
            content_id=content_id,
            content_type=content_type,
            tags=[],
            auto_generated=True,
            success=False,
            error=str(e),
        )


@router.post("/batch")
async def batch_tag_content(
    request: BatchTaggingRequest,
    service: Annotated[TaggingService, Depends(get_tagging_service)],
) -> BatchTaggingResponse:
    """Tag multiple content items in batch.

    Args:
        request: Batch tagging request with content items
        service: Tagging service instance

    Returns
    -------
        BatchTaggingResponse with results
    """
    result = await service.batch_tag_content(request.items)

    return BatchTaggingResponse(
        results=[
            TaggingResponse(
                content_id=UUID(r["content_id"]),
                content_type=r["content_type"],
                tags=r["tags"],
                auto_generated=True,
                success=r["success"],
                error=r.get("error"),
            )
            for r in result["results"]
        ],
        total=result["total"],
        successful=result["successful"],
        failed=result["failed"],
    )


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


@router.post("/suggest")
async def suggest_tags(
    request: TagSuggestionRequest,
    auth: CurrentAuth,
    service: Annotated[TaggingService, Depends(get_tagging_service)],
) -> list[str]:
    """Suggest tags for content without storing them.

    Args:
        request: Tag suggestion request
        service: Tagging service instance

    Returns
    -------
        List of suggested tag names
    """
    return await service.suggest_tags(
        content_preview=request.content_preview,
        _user_id=auth.user_id,
        _content_type=request.content_type,
        title=request.title,
    )
