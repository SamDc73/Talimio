import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from src.auth import CurrentAuth
from src.content.schemas import ContentListResponse, ContentType
from src.content.services.content_service import ContentService
from src.courses.facade import CoursesFacade
from src.courses.schemas import LessonResponse
from src.database.session import DbSession
from src.middleware.security import api_rate_limit


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1/content", tags=["content"])


def get_course_service(
    _auth: CurrentAuth,
    _session: DbSession,
) -> CoursesFacade:
    """Get course orchestrator service instance."""
    return CoursesFacade()


@router.get("")
async def get_all_content(
    _request: Request,
    _response: Response,
    auth: CurrentAuth,
    db: DbSession,
    search: Annotated[str | None, Query(description="Search term for filtering content")] = None,
    content_type: Annotated[ContentType | None, Query(description="Filter by content type")] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    include_archived: Annotated[bool, Query(description="Include archived content")] = False,
) -> ContentListResponse:
    """
    List all content across different types (videos, flashcards, books, courses).

    Returns a unified list of content items with consistent structure.
    Uses ultra-optimized single query with database-level sorting and pagination.
    Requires authentication when Supabase auth is configured.
    """
    logger.info(f"🔍 Getting content for authenticated user: {auth.user_id}")
    content_service = ContentService(session=db)
    return await content_service.list_content_fast(
        user_id=auth.user_id,
        search=search,
        content_type=content_type,
        page=page,
        page_size=page_size,
        include_archived=include_archived,
    )


@router.patch("/{content_type}/{content_id}/archive", status_code=204)
@api_rate_limit
async def archive_content_endpoint(
    request: Request,  # noqa: ARG001
    content_type: ContentType,
    content_id: UUID,
    auth: CurrentAuth,
    db: DbSession,
) -> None:
    """
    Archive a content item by type and ID.

    Supports: youtube (videos), flashcards, book, course
    Requires authentication when Supabase auth is configured.
    """
    from src.content.services.content_archive_service import ContentArchiveService

    try:
        await ContentArchiveService.archive_content(db, content_type, content_id, auth.user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.patch("/{content_type}/{content_id}/unarchive", status_code=204)
@api_rate_limit
async def unarchive_content_endpoint(
    request: Request,  # noqa: ARG001
    content_type: ContentType,
    content_id: UUID,
    auth: CurrentAuth,
    db: DbSession,
) -> None:
    """
    Unarchive a content item by type and ID.

    Supports: youtube (videos), flashcards, book, course
    Requires authentication when Supabase auth is configured.
    """
    from src.content.services.content_archive_service import ContentArchiveService

    try:
        await ContentArchiveService.unarchive_content(db, content_type, content_id, auth.user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/{content_type}/{content_id}", status_code=204)
@api_rate_limit
async def delete_content(
    request: Request,  # noqa: ARG001
    content_type: ContentType,
    content_id: str,
    auth: CurrentAuth,
    db: DbSession,
) -> None:
    """
    Delete a content item by type and ID.

    Supports: youtube (videos), flashcards, book, course
    Requires authentication when Supabase auth is configured.
    """
    content_service = ContentService(session=db)
    try:
        await content_service.delete_content(
            content_type=content_type,
            content_id=content_id,
            user_id=auth.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/test-books")
async def test_books_endpoint(
    auth: CurrentAuth,
    db: DbSession,
) -> dict:
    """Test endpoint to debug book progress fetching."""
    from sqlalchemy import text

    query = """
        SELECT
            b.id::text,
            b.title,
            COALESCE(up.progress_percentage, 0) as progress
        FROM books b
        LEFT JOIN user_progress up
          ON up.content_id = b.id
         AND up.user_id = :user_id
         AND up.content_type = 'book'
        WHERE b.user_id = :user_id
        LIMIT 5
    """

    result = await db.execute(text(query), {"user_id": str(auth.user_id)})
    books = [{"id": row[0], "title": row[1], "progress": row[2]} for row in result]

    return {"books": books}


@router.get("/lessons/{lesson_id}")
async def get_lesson_by_id(
    lesson_id: UUID,
    course_service: Annotated[CoursesFacade, Depends(get_course_service)],
    auth: CurrentAuth,
    db: DbSession,
    generate: Annotated[bool, Query(description="Auto-generate if lesson doesn't exist")] = False,
) -> LessonResponse:
    """
    Get a lesson by ID alone (without requiring course ID).

    This endpoint finds the lesson across all courses and returns it.
    Useful for simplified /lesson/{uuid} routing.
    """
    # First, try to find which course this lesson belongs to
    try:
        # Query the database to find the course that contains this lesson
        from sqlalchemy import text

        query = text("""
            SELECT course_id
            FROM lessons
            WHERE id = :lesson_id
            LIMIT 1
        """)

        result = await db.execute(query, {"lesson_id": lesson_id})

        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Lesson not found")

        course_id = row[0]

        # Now fetch the lesson using the existing simplified endpoint
        return await course_service.get_lesson_simplified(course_id, lesson_id, generate, auth.user_id)

    except HTTPException as e:
        logger.exception(f"Error fetching lesson {lesson_id}: {e}")
        # Re-raise HTTP exceptions (e.g., 401/404) instead of masking as 500
        raise
    except Exception as e:
        logger.exception(f"Error fetching lesson {lesson_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch lesson") from e
