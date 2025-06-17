from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Query

from src.content.schemas import ContentListResponse, ContentType
from src.content.service import (
    archive_content,
    delete_content,
    get_content_stats,
    list_archived_content,
    list_content_fast,
    unarchive_content,
)


router = APIRouter(prefix="/api/v1/content", tags=["content"])


@router.get("")
async def get_all_content(
    search: Annotated[str | None, Query(description="Search term for filtering content")] = None,
    content_type: Annotated[ContentType | None, Query(description="Filter by content type")] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
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
    )


@router.patch("/{content_type}/{content_id}/archive")
async def archive_content_item(
    content_type: Annotated[ContentType, Path(description="Type of content to archive")],
    content_id: Annotated[str, Path(description="ID of content to archive")],
) -> dict[str, str]:
    """Archive a content item by type and ID."""
    try:
        await archive_content(content_type, content_id)
        return {"message": f"Content {content_id} archived successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to archive content: {e!s}")


@router.patch("/{content_type}/{content_id}/unarchive")
async def unarchive_content_item(
    content_type: Annotated[ContentType, Path(description="Type of content to unarchive")],
    content_id: Annotated[str, Path(description="ID of content to unarchive")],
) -> dict[str, str]:
    """Unarchive a content item by type and ID."""
    try:
        await unarchive_content(content_type, content_id)
        return {"message": f"Content {content_id} unarchived successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to unarchive content: {e!s}")


@router.get("/archived")
async def get_archived_content(
    search: Annotated[str | None, Query(description="Search term for filtering content")] = None,
    content_type: Annotated[ContentType | None, Query(description="Filter by content type")] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
) -> ContentListResponse:
    """
    List only archived content across different types.

    Returns a unified list of archived content items with consistent structure.
    """
    return await list_archived_content(
        search=search,
        content_type=content_type,
        page=page,
        page_size=page_size,
    )


@router.get("/stats")
async def get_dashboard_stats() -> dict[str, Any]:
    """
    Get dashboard statistics for all content types.

    Returns counts of total, archived, and active content by type.
    """
    return await get_content_stats()


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
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete content: {e!s}")
