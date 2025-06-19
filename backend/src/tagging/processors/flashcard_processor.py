"""Flashcard content processor for tagging."""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.flashcards.models import FlashcardCard


logger = logging.getLogger(__name__)


async def process_flashcard_for_tagging(
    content_id: UUID,
    session: AsyncSession,
) -> dict[str, str] | None:
    """Process flashcard for tagging.

    Args:
        content_id: UUID of the flashcard
        session: Database session

    Returns
    -------
        Dictionary with flashcard data or None if not found
    """
    try:
        # Get flashcard data
        result = await session.execute(
            select(FlashcardCard.question, FlashcardCard.answer, FlashcardCard.hint).where(
                FlashcardCard.id == content_id
            )
        )

        flashcard = result.first()
        if not flashcard:
            logger.warning(f"Flashcard {content_id} not found")
            return None

        # Prepare content for tagging
        content_preview = f"Question: {flashcard.question}\nAnswer: {flashcard.answer}"
        if flashcard.hint:
            content_preview += f"\nHint: {flashcard.hint}"

        return {
            "question": flashcard.question,
            "answer": flashcard.answer,
            "hint": flashcard.hint or "",
            "content_preview": content_preview,
        }

    except Exception as e:
        logger.exception(f"Error processing flashcard {content_id} for tagging: {e}")
        return None
