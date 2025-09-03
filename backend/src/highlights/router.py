"""
API router for highlights functionality.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import UserId
from src.database.session import get_db_session
from src.middleware.security import api_rate_limit

from .models import Highlight
from .schemas import HighlightCreate, HighlightResponse


logger = logging.getLogger(__name__)

router = APIRouter(tags=["highlights"], dependencies=[Depends(api_rate_limit)])


@router.get("/api/v1/books/{book_id}/highlights", response_model=list[HighlightResponse])
async def get_book_highlights(
    book_id: UUID,
    user_id: UserId,
    db: AsyncSession = Depends(get_db_session),
) -> list[HighlightResponse]:
    """Get all highlights for a specific book."""
    try:
        result = await db.execute(
            select(Highlight).where(
                and_(
                    Highlight.user_id == user_id,
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
        logger.error(f"Error fetching highlights for book {book_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch highlights")


@router.post(
    "/api/v1/books/{book_id}/highlights", response_model=HighlightResponse, status_code=status.HTTP_201_CREATED
)
async def create_book_highlight(
    book_id: UUID,
    highlight_create: HighlightCreate,
    user_id: UserId,
    db: AsyncSession = Depends(get_db_session),
) -> HighlightResponse:
    """Create a new highlight for a book."""
    try:
        # Create the highlight
        highlight = Highlight(
            user_id=user_id,
            content_type="book",
            content_id=book_id,
            highlight_data=highlight_create.source_data,
        )

        db.add(highlight)
        await db.commit()
        await db.refresh(highlight)

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
        logger.error(f"Error creating highlight for book {book_id}: {e}")
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create highlight")


@router.delete("/api/v1/highlights/{highlight_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_highlight(
    highlight_id: UUID,
    user_id: UserId,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a highlight by ID."""
    try:
        # Find the highlight
        result = await db.execute(
            select(Highlight).where(
                and_(
                    Highlight.id == highlight_id,
                    Highlight.user_id == user_id,
                )
            )
        )
        highlight = result.scalar_one_or_none()

        if not highlight:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Highlight not found")

        await db.delete(highlight)
        await db.commit()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting highlight {highlight_id}: {e}")
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete highlight")


@router.put("/api/v1/highlights/{highlight_id}", response_model=HighlightResponse)
async def update_highlight(
    highlight_id: UUID,
    highlight_update: HighlightCreate,
    user_id: UserId,
    db: AsyncSession = Depends(get_db_session),
) -> HighlightResponse:
    """Update a highlight by ID."""
    try:
        # Find the highlight
        result = await db.execute(
            select(Highlight).where(
                and_(
                    Highlight.id == highlight_id,
                    Highlight.user_id == user_id,
                )
            )
        )
        highlight = result.scalar_one_or_none()

        if not highlight:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Highlight not found")

        # Update the highlight data
        highlight.highlight_data = highlight_update.source_data

        await db.commit()
        await db.refresh(highlight)

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
        logger.error(f"Error updating highlight {highlight_id}: {e}")
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update highlight")
