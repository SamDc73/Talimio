import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from src.auth.dependencies import get_current_user_optional
from src.auth.models import User
from src.content.schemas import ContentListResponse, ContentType
from src.content.service import (
    archive_content,
    delete_content,
    list_content_fast,
    unarchive_content,
)


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1/content", tags=["content"])


@router.get("")
async def get_all_content(
    search: Annotated[str | None, Query(description="Search term for filtering content")] = None,
    content_type: Annotated[ContentType | None, Query(description="Filter by content type")] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    include_archived: Annotated[bool, Query(description="Include archived content")] = False,
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
) -> ContentListResponse:
    """
    List all content across different types (videos, flashcards, books, roadmaps).

    Returns a unified list of content items with consistent structure.
    Uses ultra-optimized single query with database-level sorting and pagination.
    """
    return await list_content_fast(
        search=search,
        content_type=content_type,
        page=page,
        page_size=page_size,
        include_archived=include_archived,
        current_user_id=str(current_user.id) if current_user else None,
    )


@router.patch("/{content_type}/{content_id}/archive")
async def archive_content_item(
    content_type: Annotated[ContentType, Path(description="Type of content to archive")],
    content_id: Annotated[str, Path(description="ID of content to archive")],
) -> dict[str, str]:
    """Archive a content item by type and ID."""
    logger.info(f"🗃️ Archive request: {content_type} {content_id}")
    try:
        await archive_content(content_type, content_id)
        logger.info(f"✅ Successfully archived {content_type} {content_id}")
        return {"message": f"Content {content_id} archived successfully"}
    except ValueError as e:
        logger.exception("❌ Archive failed - ValueError")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("❌ Archive failed - Exception")
        raise HTTPException(status_code=500, detail=f"Failed to archive content: {e!s}") from e


@router.patch("/{content_type}/{content_id}/unarchive")
async def unarchive_content_item(
    content_type: Annotated[ContentType, Path(description="Type of content to unarchive")],
    content_id: Annotated[str, Path(description="ID of content to unarchive")],
) -> dict[str, str]:
    """Unarchive a content item by type and ID."""
    logger.info(f"📤 Unarchive request: {content_type} {content_id}")
    try:
        await unarchive_content(content_type, content_id)
        logger.info(f"✅ Successfully unarchived {content_type} {content_id}")
        return {"message": f"Content {content_id} unarchived successfully"}
    except ValueError as e:
        logger.exception("❌ Unarchive failed - ValueError")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("❌ Unarchive failed - Exception")
        raise HTTPException(status_code=500, detail=f"Failed to unarchive content: {e!s}") from e


@router.delete("/{content_type}/{content_id}")
async def delete_content_item(
    content_type: Annotated[ContentType, Path(description="Type of content to delete")],
    content_id: Annotated[str, Path(description="ID of content to delete")],
) -> dict[str, str]:
    """Delete a content item by type and ID."""
    try:
        await delete_content(content_type, content_id)
        return {"message": f"Content {content_id} deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete content: {e!s}") from e
