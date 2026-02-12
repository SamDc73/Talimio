"""API router for highlights functionality."""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import and_, select

from src.auth import CurrentAuth

from .models import Highlight
from .schemas import HighlightCreate, HighlightResponse


logger = logging.getLogger(__name__)

router = APIRouter(tags=["highlights"])


@router.get("/api/v1/books/{book_id}/highlights")
async def get_book_highlights(
    book_id: UUID,
    auth: CurrentAuth,
) -> list[HighlightResponse]:
    """Get all highlights for a specific book."""
    try:
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
    except Exception as e:
        logger.exception(f"Error fetching highlights for book {book_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch highlights"
        ) from e


@router.post("/api/v1/books/{book_id}/highlights", status_code=status.HTTP_201_CREATED)
async def create_book_highlight(
    book_id: UUID,
    highlight_create: HighlightCreate,
    auth: CurrentAuth,
) -> HighlightResponse:
    """Create a new highlight for a book."""
    try:
        # Create the highlight
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
    except Exception as e:
        logger.exception(f"Error creating highlight for book {book_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create highlight"
        ) from e


@router.delete("/api/v1/highlights/{highlight_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_highlight(
    highlight_id: UUID,
    auth: CurrentAuth,
) -> None:
    """Delete a highlight by ID."""
    try:
        # Find the highlight
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

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting highlight {highlight_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete highlight"
        ) from e


@router.put("/api/v1/highlights/{highlight_id}")
async def update_highlight(
    highlight_id: UUID,
    highlight_update: HighlightCreate,
    auth: CurrentAuth,
) -> HighlightResponse:
    """Update a highlight by ID."""
    try:
        # Find the highlight
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

        # Update the highlight data
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
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating highlight {highlight_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update highlight"
        ) from e
