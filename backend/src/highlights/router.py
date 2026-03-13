"""API router for highlights functionality."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import and_, select

from src.auth import CurrentAuth

from .models import Highlight
from .schemas import HighlightCreate, HighlightResponse


router = APIRouter(prefix="/api/v1", tags=["highlights"])


@router.get("/books/{book_id}/highlights")
async def get_book_highlights(
    book_id: uuid.UUID,
    auth: CurrentAuth,
) -> list[HighlightResponse]:
    """Get all highlights for a specific book."""
    result = await auth.session.execute(
        select(Highlight).where(
            and_(
                Highlight.user_id == auth.user_id,
                Highlight.content_type == "book",
                Highlight.content_id == book_id,
            )
        )
    )
    highlights = result.scalars().all()

    return [
        HighlightResponse(
            id=h.id,
            user_id=h.user_id,
            content_type=h.content_type,
            content_id=h.content_id,
            highlight_data=h.highlight_data,
            created_at=h.created_at,
            updated_at=h.updated_at,
        )
        for h in highlights
    ]


@router.post("/books/{book_id}/highlights", status_code=status.HTTP_201_CREATED)
async def create_book_highlight(
    book_id: uuid.UUID,
    highlight_create: HighlightCreate,
    auth: CurrentAuth,
) -> HighlightResponse:
    """Create a new highlight for a book."""
    highlight = Highlight(
        user_id=auth.user_id,
        content_type="book",
        content_id=book_id,
        highlight_data=highlight_create.source_data,
    )

    auth.session.add(highlight)
    await auth.session.flush()
    await auth.session.refresh(highlight)

    return HighlightResponse(
        id=highlight.id,
        user_id=highlight.user_id,
        content_type=highlight.content_type,
        content_id=highlight.content_id,
        highlight_data=highlight.highlight_data,
        created_at=highlight.created_at,
        updated_at=highlight.updated_at,
    )


@router.delete("/highlights/{highlight_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_highlight(
    highlight_id: uuid.UUID,
    auth: CurrentAuth,
) -> None:
    """Delete a highlight by ID."""
    result = await auth.session.execute(
        select(Highlight).where(
            and_(
                Highlight.id == highlight_id,
                Highlight.user_id == auth.user_id,
            )
        )
    )
    highlight = result.scalar_one_or_none()

    if not highlight:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Highlight not found")

    await auth.session.delete(highlight)
    await auth.session.flush()


@router.put("/highlights/{highlight_id}")
async def update_highlight(
    highlight_id: uuid.UUID,
    highlight_update: HighlightCreate,
    auth: CurrentAuth,
) -> HighlightResponse:
    """Update a highlight by ID."""
    result = await auth.session.execute(
        select(Highlight).where(
            and_(
                Highlight.id == highlight_id,
                Highlight.user_id == auth.user_id,
            )
        )
    )
    highlight = result.scalar_one_or_none()

    if not highlight:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Highlight not found")

    highlight.highlight_data = highlight_update.source_data

    await auth.session.flush()
    await auth.session.refresh(highlight)

    return HighlightResponse(
        id=highlight.id,
        user_id=highlight.user_id,
        content_type=highlight.content_type,
        content_id=highlight.content_id,
        highlight_data=highlight.highlight_data,
        created_at=highlight.created_at,
        updated_at=highlight.updated_at,
    )
