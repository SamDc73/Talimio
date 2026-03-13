import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response, status

from src.auth import CurrentAuth
from src.content.schemas import ContentListResponse, ContentType, normalize_content_type
from src.content.services.content_service import ContentService


router = APIRouter(prefix="/api/v1/content", tags=["content"])


@router.get("")
async def get_all_content(
    _request: Request,
    _response: Response,
    auth: CurrentAuth,
    search: Annotated[str | None, Query(description="Search term for filtering content")] = None,
    content_type: Annotated[ContentType | None, Query(description="Filter by content type")] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    include_archived: Annotated[bool, Query(description="Include archived content")] = False,
) -> ContentListResponse:
    """
    List all content across different types (videos, books, courses).

    Returns a unified list of content items with consistent structure.
    Uses ultra-optimized single query with database-level sorting and pagination.
    Requires authentication when local auth is configured.
    """
    content_service = ContentService(session=auth.session)
    return await content_service.list_content_fast(
        user_id=auth.user_id,
        search=search,
        content_type=content_type,
        page=page,
        page_size=page_size,
        include_archived=include_archived,
    )


@router.patch("/{content_type}/{content_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
async def archive_content(
    content_type: ContentType,
    content_id: uuid.UUID,
    auth: CurrentAuth,
) -> None:
    """Archive a content item by type and ID."""
    from src.content.services.content_archive_service import ContentArchiveService

    normalized_content_type = normalize_content_type(content_type)

    await ContentArchiveService.archive_content(auth.session, normalized_content_type, content_id, auth.user_id)


@router.patch("/{content_type}/{content_id}/unarchive", status_code=status.HTTP_204_NO_CONTENT)
async def unarchive_content(
    content_type: ContentType,
    content_id: uuid.UUID,
    auth: CurrentAuth,
) -> None:
    """Unarchive a content item by type and ID."""
    from src.content.services.content_archive_service import ContentArchiveService

    normalized_content_type = normalize_content_type(content_type)

    await ContentArchiveService.unarchive_content(auth.session, normalized_content_type, content_id, auth.user_id)


@router.delete("/{content_type}/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_content(
    content_type: ContentType,
    content_id: uuid.UUID,
    auth: CurrentAuth,
) -> None:
    """Delete a content item by type and ID."""
    content_service = ContentService(session=auth.session)
    normalized_content_type = normalize_content_type(content_type)

    await content_service.delete_content(
        content_type=normalized_content_type,
        content_id=content_id,
        user_id=auth.user_id,
    )
