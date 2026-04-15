"""API router for highlights functionality."""

import uuid

from fastapi import APIRouter, status

from src.auth import CurrentAuth

from .schemas import HighlightCreate, HighlightResponse
from .service import BookHighlightService


router = APIRouter(prefix="/api/v1", tags=["highlights"])


@router.get("/books/{book_id}/highlights")
async def get_book_highlights(
    book_id: uuid.UUID,
    auth: CurrentAuth,
) -> list[HighlightResponse]:
    """Get all highlights for a specific book."""
    return await BookHighlightService(auth.session).get_highlights(book_id, auth.user_id)


@router.post("/books/{book_id}/highlights", status_code=status.HTTP_201_CREATED)
async def create_book_highlight(
    book_id: uuid.UUID,
    highlight_create: HighlightCreate,
    auth: CurrentAuth,
) -> HighlightResponse:
    """Create a new highlight for a book."""
    return await BookHighlightService(auth.session).create_highlight(
        book_id,
        auth.user_id,
        highlight_create.source_data,
    )


@router.delete("/highlights/{highlight_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_highlight(
    highlight_id: uuid.UUID,
    auth: CurrentAuth,
) -> None:
    """Delete a highlight by ID."""
    await BookHighlightService(auth.session).delete_highlight(highlight_id, auth.user_id)


@router.put("/highlights/{highlight_id}")
async def update_highlight(
    highlight_id: uuid.UUID,
    highlight_update: HighlightCreate,
    auth: CurrentAuth,
) -> HighlightResponse:
    """Update a highlight by ID."""
    return await BookHighlightService(auth.session).update_highlight(
        highlight_id,
        auth.user_id,
        highlight_update.source_data,
    )
