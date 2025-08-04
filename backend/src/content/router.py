import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from src.auth import UserId
from src.content.schemas import ContentListResponse, ContentType
from src.content.services.content_service import ContentService
from src.courses.schemas import LessonResponse
from src.courses.services.course_service import CourseService
from src.database.session import DbSession, get_db_session


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1/content", tags=["content"])


def get_course_service(
    user_id: UserId,
    session: DbSession,
) -> CourseService:
    """Get course service instance."""
    return CourseService(session, user_id)


@router.get("")
async def get_all_content(
    _request: Request,
    response: Response,
    user_id: UserId,
    db: DbSession,
    search: Annotated[str | None, Query(description="Search term for filtering content")] = None,
    content_type: Annotated[ContentType | None, Query(description="Filter by content type")] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    include_archived: Annotated[bool, Query(description="Include archived content")] = False,
) -> ContentListResponse:
    """
    List all content across different types (videos, flashcards, books, roadmaps).

    Returns a unified list of content items with consistent structure.
    Uses ultra-optimized single query with database-level sorting and pagination.
    Requires authentication when Supabase auth is configured.
    """
    logger.info(f"🔍 Getting content for authenticated user: {user_id}")
    content_service = ContentService(session=db)
    content = await content_service.list_content_fast(
        user_id=user_id,
        search=search,
        content_type=content_type,
        page=page,
        page_size=page_size,
        include_archived=include_archived,
    )

    # Add caching headers - content metadata doesn't change frequently
    response.headers["Cache-Control"] = "private, max-age=30"  # 30 seconds cache

    return content


@router.delete("/{content_type}/{content_id}", status_code=204)
async def delete_content(
    content_type: ContentType,
    content_id: str,
    user_id: UserId,
    db: DbSession,
) -> None:
    """
    Delete a content item by type and ID.

    Supports: youtube (videos), flashcards, book, roadmap (courses)
    Requires authentication when Supabase auth is configured.
    """
    content_service = ContentService(session=db)
    await content_service.delete_content(
        content_type=content_type,
        content_id=content_id,
        user_id=user_id,
    )


@router.get("/test-books")
async def test_books_endpoint(
    user_id: UserId,
    db: DbSession,
) -> dict:
    """Test endpoint to debug book progress fetching."""
    from sqlalchemy import text

    query = """
        SELECT
            b.id::text,
            b.title,
            COALESCE(bp.progress_percentage, 0) as progress
        FROM books b
        LEFT JOIN book_progress bp ON b.id = bp.book_id AND bp.user_id = :user_id
        WHERE b.user_id = :user_id
        LIMIT 5
    """

    result = await db.execute(text(query), {"user_id": user_id})
    books = [{"id": row[0], "title": row[1], "progress": row[2]} for row in result]

    return {"books": books}


@router.get("/lessons/{lesson_id}")
async def get_lesson_by_id(
    lesson_id: UUID,
    course_service: Annotated[CourseService, Depends(get_course_service)],
    _user_id: UserId,
    session: Annotated[object, Depends(get_db_session)],
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
            SELECT roadmap_id
            FROM nodes
            WHERE id = :lesson_id
            LIMIT 1
        """)

        result = await session.execute(query, {"lesson_id": lesson_id})

        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Lesson not found")

        course_id = row[0]

        # Now fetch the lesson using the existing simplified endpoint
        return await course_service.get_lesson_simplified(course_id, lesson_id, generate)

    except Exception as e:
        logger.exception(f"Error fetching lesson {lesson_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch lesson") from e
