"""Flashcard content service extending BaseContentService."""

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.base_service import BaseContentService
from src.database.session import async_session_maker
from src.flashcards.models import FlashcardDeck


logger = logging.getLogger(__name__)


class FlashcardContentService(BaseContentService):
    """Flashcard service with shared content behavior."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        super().__init__()
        self.session = session

    def _get_content_type(self) -> str:
        """Return the content type for this service."""
        return "flashcard"

    async def _do_create(self, data: dict, user_id: UUID) -> FlashcardDeck:
        """Create a new flashcard deck."""
        async with async_session_maker() as session:
            # Convert tags to JSON if present
            if "tags" in data and data["tags"] is not None:
                data["tags"] = json.dumps(data["tags"])

            # Create flashcard deck instance
            deck = FlashcardDeck(**data, user_id=user_id, created_at=datetime.now(UTC), updated_at=datetime.now(UTC))

            session.add(deck)
            await session.commit()
            await session.refresh(deck)

            logger.info(f"Created flashcard deck {deck.id} for user {user_id}")
            return deck

    async def _do_update(self, content_id: UUID, data: dict, user_id: UUID) -> FlashcardDeck:
        """Update an existing flashcard deck."""
        async with async_session_maker() as session:
            # Get the deck
            query = select(FlashcardDeck).where(FlashcardDeck.id == content_id, FlashcardDeck.user_id == user_id)
            result = await session.execute(query)
            deck = result.scalar_one_or_none()

            if not deck:
                msg = f"Flashcard deck {content_id} not found"
                raise ValueError(msg)

            # Update fields
            for field, value in data.items():
                if field == "tags" and value is not None:
                    setattr(deck, field, json.dumps(value))
                else:
                    setattr(deck, field, value)

            deck.updated_at = datetime.now(UTC)

            await session.commit()
            await session.refresh(deck)

            logger.info(f"Updated flashcard deck {deck.id}")
            return deck

    async def _do_delete(self, content_id: UUID, user_id: UUID) -> bool:
        """Delete a flashcard deck."""
        async with async_session_maker() as session:
            # Get the deck
            query = select(FlashcardDeck).where(FlashcardDeck.id == content_id, FlashcardDeck.user_id == user_id)
            result = await session.execute(query)
            deck = result.scalar_one_or_none()

            if not deck:
                return False

            # Delete the deck (cascade will handle related cards)
            await session.delete(deck)
            await session.commit()

            logger.info(f"Deleted flashcard deck {content_id}")
            return True

    def _needs_ai_processing(self, content: FlashcardDeck) -> bool:
        """Check if flashcard deck needs AI processing after creation."""
        # Flashcards might need AI for generation from content
        return hasattr(content, "generation_status") and content.generation_status == "pending"

    def _needs_ai_reprocessing(self, content: FlashcardDeck, updated_data: dict) -> bool:
        """Check if flashcard deck needs AI reprocessing after update."""
        # Reprocess if source content changes
        _ = content
        significant_fields = {"source_content", "difficulty_level"}
        return any(field in updated_data for field in significant_fields)

    async def _update_progress(self, content_id: UUID, user_id: UUID, status: str) -> None:
        """Update progress tracking for flashcard deck."""
        _ = user_id
        try:
            # For flashcards, we track study progress separately
            # This is just for creation status
            logger.info(f"Flashcard deck {content_id} status: {status}")
        except Exception as e:
            logger.exception(f"Failed to update flashcard progress: {e}")
