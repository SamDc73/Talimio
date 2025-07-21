import logging
from typing import Annotated

from fastapi import APIRouter, Query

from src.auth.dependencies import CurrentUser
from src.content.schemas import ContentListResponse, ContentType
from src.content.services.content_service import ContentService


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1/content", tags=["content"])


@router.get("")
async def get_all_content(
    search: Annotated[str | None, Query(description="Search term for filtering content")] = None,
    content_type: Annotated[ContentType | None, Query(description="Filter by content type")] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    include_archived: Annotated[bool, Query(description="Include archived content")] = False,
    current_user: CurrentUser = None,
) -> ContentListResponse:
    """
    List all content across different types (videos, flashcards, books, roadmaps).

    Returns a unified list of content items with consistent structure.
    Uses ultra-optimized single query with database-level sorting and pagination.
    """
    return await ContentService.list_content_fast(
        search=search,
        content_type=content_type,
        page=page,
        page_size=page_size,
        include_archived=include_archived,
        current_user_id=str(current_user.id) if current_user else None,
    )


@router.delete("/{content_type}/{content_id}", status_code=204)
async def delete_content(
    content_type: ContentType,
    content_id: str,
    current_user: CurrentUser = None,
) -> None:
    """
    Delete a content item by type and ID.

    Supports: youtube (videos), flashcards, book, roadmap (courses)
    """
    await ContentService.delete_content(
        content_type=content_type,
        content_id=content_id,
        current_user_id=str(current_user.id) if current_user else None,
    )
