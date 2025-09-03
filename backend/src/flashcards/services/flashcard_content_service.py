"""Flashcard content service for flashcard-specific operations."""

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.session import async_session_maker
from src.flashcards.models import FlashcardDeck


logger = logging.getLogger(__name__)


class FlashcardContentService:
    """Flashcard service handling flashcard-specific content operations."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session

    async def create_deck(self, data: dict, user_id: UUID) -> FlashcardDeck:
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

    async def update_deck(self, deck_id: UUID, data: dict, user_id: UUID) -> FlashcardDeck:
        """Update an existing flashcard deck."""
        async with async_session_maker() as session:
            # Get the deck
            query = select(FlashcardDeck).where(FlashcardDeck.id == deck_id, FlashcardDeck.user_id == user_id)
            result = await session.execute(query)
            deck = result.scalar_one_or_none()

            if not deck:
                msg = f"Flashcard deck {deck_id} not found"
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

    async def delete_deck(self, deck_id: UUID, user_id: UUID) -> bool:
        """Delete a flashcard deck."""
        async with async_session_maker() as session:
            # Get the deck
            query = select(FlashcardDeck).where(FlashcardDeck.id == deck_id, FlashcardDeck.user_id == user_id)
            result = await session.execute(query)
            deck = result.scalar_one_or_none()

            if not deck:
                return False

            # Delete the deck (cascade will handle related cards)
            await session.delete(deck)
            await session.commit()

            logger.info(f"Deleted flashcard deck {deck_id}")
            return True
