from typing import Annotated

from fastapi import APIRouter, Query

from src.content.schemas import ContentListResponse, ContentType
from src.content.service import list_content_fast


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
