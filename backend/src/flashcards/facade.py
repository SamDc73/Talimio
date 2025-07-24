"""
Flashcards Module Facade.

Single entry point for all flashcard-related operations.
Coordinates internal flashcard services and provides stable API for other modules.
"""

import logging
from typing import Any
from uuid import UUID

from src.ai.ai_service import get_ai_service

from .service import (
    create_card,
    delete_card,
    get_card,
    get_deck,
    get_deck_cards,
    get_decks,
    get_study_session,
    review_card,
    update_card,
    update_deck,
)
from .services.flashcard_content_service import FlashcardContentService


logger = logging.getLogger(__name__)


class FlashcardsFacade:
    """
    Single entry point for all flashcard operations.

    Coordinates internal flashcard services and provides
    stable API that won't break when internal implementation changes.
    """

    def __init__(self) -> None:
        # For now, we're using the existing service functions directly
        # In future, these could be replaced with service classes
        self._content_service = FlashcardContentService()  # New base service
        self._ai_service = get_ai_service()

    async def create_deck(self, deck_data: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        """
        Create a new flashcard deck.

        Handles deck creation and initialization.
        """
        try:
            # Use the new content service which handles tags, progress, and AI processing
            deck = await self._content_service.create_content(deck_data, user_id)

            # Event publishing will be implemented with event bus
            logger.info(f"Deck created by user {user_id}")

            return {"deck": deck, "success": True}

        except Exception as e:
            logger.exception(f"Error creating deck for user {user_id}: {e}")
            return {"error": "Failed to create deck", "success": False}

    async def create_card(self, deck_id: UUID, card_data: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        """
        Create a new flashcard.

        Handles card creation within a deck.
        """
        try:
            card = await create_card(deck_id, card_data, user_id)

            # Event publishing will be implemented with event bus
            logger.info(f"Card created in deck {deck_id} by user {user_id}")

            return {"card": card, "success": True}

        except Exception as e:
            logger.exception(f"Error creating card in deck {deck_id}: {e}")
            return {"error": "Failed to create card", "success": False}

    async def get_deck_with_cards(self, deck_id: UUID, user_id: UUID) -> dict[str, Any]:
        """
        Get deck with all its cards.

        Provides complete deck information including cards.
        """
        try:
            deck = await get_deck(deck_id, user_id)
            if not deck:
                return {"error": "Deck not found", "success": False}

            cards = await get_deck_cards(deck_id, user_id)

            # Build comprehensive response
            response = {"deck": deck, "cards": cards, "total_cards": len(cards)}

            # Event publishing deck accessed event
            logger.info(f"Deck {deck_id} accessed by user {user_id}")

            return {"data": response, "success": True}

        except Exception as e:
            logger.exception(f"Error getting deck {deck_id}: {e}")
            return {"error": "Failed to retrieve deck", "success": False}

    async def get_user_decks(self, user_id: UUID, page: int = 1, per_page: int = 20) -> dict[str, Any]:
        """
        Get all decks for a user.

        Returns list of user's flashcard decks.
        """
        try:
            result = await get_decks(user_id, page, per_page)

            return {"decks": result.items, "total": result.total, "pages": result.pages, "success": True}

        except Exception as e:
            logger.exception(f"Error getting decks for user {user_id}: {e}")
            return {"error": "Failed to get decks", "success": False}

    async def get_study_session(self, deck_id: UUID, user_id: UUID, limit: int = 20) -> dict[str, Any]:
        """
        Get cards for study session.

        Returns cards that are due for review.
        """
        try:
            session = await get_study_session(deck_id, user_id, limit)

            # Event publishing study session started event
            logger.info(f"Study session started for deck {deck_id} by user {user_id}")

            return {"session": session, "success": True}

        except Exception as e:
            logger.exception(f"Error getting study session for deck {deck_id}: {e}")
            return {"error": "Failed to get study session", "success": False}

    async def review_card(self, card_id: UUID, review_data: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        """
        Submit review for a flashcard.

        Updates card scheduling based on review rating.
        """
        try:
            review_result = await review_card(card_id, review_data, user_id)

            # Event publishing review event for analytics
            logger.info(f"Card {card_id} reviewed by user {user_id}")

            return {"review": review_result, "success": True}

        except Exception as e:
            logger.exception(f"Error reviewing card {card_id}: {e}")
            return {"error": "Failed to submit review", "success": False}

    async def update_deck(self, deck_id: UUID, deck_data: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        """Update deck information."""
        try:
            updated_deck = await update_deck(deck_id, deck_data, user_id)

            return {"deck": updated_deck, "success": True}

        except Exception as e:
            logger.exception(f"Error updating deck {deck_id}: {e}")
            return {"error": "Failed to update deck", "success": False}

    async def update_card(self, card_id: UUID, card_data: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        """Update card content."""
        try:
            updated_card = await update_card(card_id, card_data, user_id)

            return {"card": updated_card, "success": True}

        except Exception as e:
            logger.exception(f"Error updating card {card_id}: {e}")
            return {"error": "Failed to update card", "success": False}

    async def delete_deck(self, deck_id: UUID, user_id: UUID) -> dict[str, Any]:
        """Delete deck and all its cards."""
        try:
            # Use content service which handles cleanup of tags and associated data
            success = await self._content_service.delete_content(deck_id, user_id)

            if success:
                # Event publishing deletion event
                logger.info(f"Deck {deck_id} deleted by user {user_id}")

            return {"success": success}

        except Exception as e:
            logger.exception(f"Error deleting deck {deck_id}: {e}")
            return {"error": "Failed to delete deck", "success": False}

    async def delete_card(self, card_id: UUID, user_id: UUID) -> dict[str, Any]:
        """Delete a single card."""
        try:
            await delete_card(card_id, user_id)

            # Event publishing deletion event
            logger.info(f"Card {card_id} deleted by user {user_id}")

            return {"success": True}

        except Exception as e:
            logger.exception(f"Error deleting card {card_id}: {e}")
            return {"error": "Failed to delete card", "success": False}

    # AI operations
    async def generate_flashcards_from_content(
        self, user_id: UUID, content: str, count: int = 10
    ) -> list[dict[str, Any]]:
        """Generate flashcards from provided content using AI."""
        try:
            return await self._ai_service.process_content(
                content_type="flashcard", action="generate", user_id=user_id, content=content, count=count
            )
        except Exception as e:
            logger.exception(f"Error generating flashcards for user {user_id}: {e}")
            raise

    async def get_card_hint(self, card_id: UUID, user_id: UUID) -> str:
        """Get a hint for a flashcard."""
        try:
            # Get card details first
            card = await get_card(card_id, user_id)
            if not card:
                msg = "Card not found"
                raise ValueError(msg)

            return await self._ai_service.process_content(
                content_type="flashcard",
                action="hint",
                user_id=user_id,
                card_id=str(card_id),
                front=card.get("front", ""),
                back=card.get("back", ""),
            )
        except Exception as e:
            logger.exception(f"Error getting hint for card {card_id}: {e}")
            raise

    async def explain_card_concept(self, card_id: UUID, user_id: UUID) -> str:
        """Get a detailed explanation of the flashcard concept."""
        try:
            # Get card details first
            card = await get_card(card_id, user_id)
            if not card:
                msg = "Card not found"
                raise ValueError(msg)

            return await self._ai_service.process_content(
                content_type="flashcard",
                action="explain",
                user_id=user_id,
                card_id=str(card_id),
                front=card.get("front", ""),
                back=card.get("back", ""),
            )
        except Exception as e:
            logger.exception(f"Error explaining card {card_id}: {e}")
            raise
