"""API router for highlights across books, videos, and lessons."""

import uuid

from fastapi import APIRouter, status

from src.auth import CurrentAuth

from .schemas import HighlightCreate, HighlightResponse
from .service import HighlightService


# Highlights own the per-content collection routes and the standalone highlight routes.
router = APIRouter(prefix="/api/v1", tags=["highlights"])


@router.get("/books/{book_id}/highlights")
async def list_book_highlights(book_id: uuid.UUID, auth: CurrentAuth) -> list[HighlightResponse]:
    """List every highlight for a book."""
    return await HighlightService(auth.session).list_book_highlights(book_id, auth.user_id)


@router.post("/books/{book_id}/highlights", status_code=status.HTTP_201_CREATED)
async def create_book_highlight(book_id: uuid.UUID, highlight: HighlightCreate, auth: CurrentAuth) -> HighlightResponse:
    """Create a highlight for a book."""
    return await HighlightService(auth.session).create_book_highlight(book_id, auth.user_id, highlight.highlight_data)


@router.get("/videos/{video_id}/highlights")
async def list_video_highlights(video_id: uuid.UUID, auth: CurrentAuth) -> list[HighlightResponse]:
    """List every highlight for a video."""
    return await HighlightService(auth.session).list_video_highlights(video_id, auth.user_id)


@router.post("/videos/{video_id}/highlights", status_code=status.HTTP_201_CREATED)
async def create_video_highlight(
    video_id: uuid.UUID, highlight: HighlightCreate, auth: CurrentAuth
) -> HighlightResponse:
    """Create a highlight for a video."""
    return await HighlightService(auth.session).create_video_highlight(video_id, auth.user_id, highlight.highlight_data)


@router.get("/courses/{course_id}/lessons/{lesson_id}/highlights")
async def list_lesson_highlights(
    course_id: uuid.UUID, lesson_id: uuid.UUID, auth: CurrentAuth
) -> list[HighlightResponse]:
    """List every highlight for a lesson."""
    return await HighlightService(auth.session).list_lesson_highlights(course_id, lesson_id, auth.user_id)


@router.post("/courses/{course_id}/lessons/{lesson_id}/highlights", status_code=status.HTTP_201_CREATED)
async def create_lesson_highlight(
    course_id: uuid.UUID, lesson_id: uuid.UUID, highlight: HighlightCreate, auth: CurrentAuth
) -> HighlightResponse:
    """Create a highlight for a lesson."""
    return await HighlightService(auth.session).create_lesson_highlight(
        course_id, lesson_id, auth.user_id, highlight.highlight_data
    )


@router.put("/highlights/{highlight_id}")
async def update_highlight(highlight_id: uuid.UUID, highlight: HighlightCreate, auth: CurrentAuth) -> HighlightResponse:
    """Update a highlight by id."""
    return await HighlightService(auth.session).update_highlight(highlight_id, auth.user_id, highlight.highlight_data)


@router.delete("/highlights/{highlight_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_highlight(highlight_id: uuid.UUID, auth: CurrentAuth) -> None:
    """Delete a highlight by id."""
    await HighlightService(auth.session).delete_highlight(highlight_id, auth.user_id)
