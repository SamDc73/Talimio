import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from src.auth.dependencies import UserId
from src.config.settings import get_settings

from .facade import FlashcardsFacade
from .schemas import (
    CardListResponse,
    DeckListResponse,
    FlashcardCardCreate,
    FlashcardCardResponse,
    FlashcardCardUpdate,
    FlashcardDeckCreate,
    FlashcardDeckResponse,
    FlashcardDeckUpdate,
    FlashcardReviewRequest,
    FlashcardReviewResponse,
    StudySessionResponse,
)
from .service import (
    create_card,
    create_deck,
    delete_card,
    delete_deck,
    get_card,
    get_deck,
    get_deck_cards,
    get_decks,
    get_study_session,
    review_card,
    update_card,
    update_deck,
)


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1/flashcards", tags=["flashcards"])


# Deck endpoints
@router.get("")
async def list_decks(
    user_id: UserId,  # Simple dependency injection
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    per_page: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
) -> DeckListResponse:
    """List all flashcard decks."""
    settings = get_settings()

    if settings.USE_MODULE_FACADES:
        try:
            facade = FlashcardsFacade()
            result = await facade.get_user_decks(user_id, page, per_page)

            if result.get("success"):
                return DeckListResponse(
                    items=result["decks"],
                    total=result["total"],
                    page=page,
                    pages=result["pages"]
                )
            logger.error(f"Facade error: {result.get('error')}")
        except Exception as e:
            logger.exception(f"Facade exception, falling back: {e}")

    # Fallback to old approach
    return await get_decks(user_id=user_id, page=page, per_page=per_page)


@router.get("/{deck_id}")
async def get_deck_endpoint(deck_id: UUID, user_id: UserId) -> FlashcardDeckResponse:
    """Get deck details."""
    return await get_deck(deck_id, user_id=user_id)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_deck_endpoint(deck_data: FlashcardDeckCreate, user_id: UserId) -> FlashcardDeckResponse:
    """Create a new deck."""
    settings = get_settings()

    if settings.USE_MODULE_FACADES:
        try:
            facade = FlashcardsFacade()
            result = await facade.create_deck(deck_data.model_dump(), user_id)

            if result.get("success"):
                return result["deck"]
            logger.error(f"Facade error: {result.get('error')}")
        except Exception as e:
            logger.exception(f"Facade exception, falling back: {e}")

    # Fallback to old approach
    return await create_deck(deck_data, user_id=user_id)


@router.put("/{deck_id}")
async def update_deck_endpoint(
    deck_id: UUID, deck_data: FlashcardDeckUpdate, user_id: UserId
) -> FlashcardDeckResponse:
    """Update deck details."""
    return await update_deck(deck_id, deck_data, user_id=user_id)


@router.delete("/{deck_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deck_endpoint(deck_id: UUID, user_id: UserId) -> None:
    """Delete a deck and all its cards."""
    await delete_deck(deck_id, user_id=user_id)


# Card endpoints
@router.get("/{deck_id}/cards")
async def get_deck_cards_endpoint(
    deck_id: UUID,
    user_id: UserId,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    per_page: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
) -> CardListResponse:
    """Get all cards in a deck."""
    return await get_deck_cards(deck_id, user_id=user_id, page=page, per_page=per_page)


@router.post("/{deck_id}/cards", status_code=status.HTTP_201_CREATED)
async def create_card_endpoint(
    deck_id: UUID, card_data: FlashcardCardCreate, user_id: UserId
) -> FlashcardCardResponse:
    """Add a card to a deck."""
    return await create_card(deck_id, card_data, user_id=user_id)


@router.put("/{deck_id}/cards/{card_id}")
async def update_card_endpoint(
    deck_id: UUID, card_id: UUID, card_data: FlashcardCardUpdate, user_id: UserId
) -> FlashcardCardResponse:
    """Update a card."""
    return await update_card(deck_id, card_id, card_data, user_id=user_id)


@router.delete("/{deck_id}/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card_endpoint(deck_id: UUID, card_id: UUID, user_id: UserId) -> None:
    """Delete a card from a deck."""
    await delete_card(deck_id, card_id, user_id=user_id)


# Review endpoints
@router.put("/{deck_id}/cards/{card_id}/review")
async def review_card_endpoint(
    deck_id: UUID, card_id: UUID, review_data: FlashcardReviewRequest, user_id: UserId
) -> FlashcardReviewResponse:
    """Submit a card review (for spaced repetition)."""
    return await review_card(deck_id, card_id, review_data, user_id=user_id)


@router.get("/{deck_id}/study")
async def get_study_session_endpoint(
    deck_id: UUID,
    user_id: UserId,
    limit: Annotated[int, Query(ge=1, le=100, description="Maximum cards to return")] = 20,
) -> StudySessionResponse:
    """Get cards due for review in a deck."""
    return await get_study_session(deck_id, user_id=user_id, limit=limit)


@router.get("/{deck_id}/cards/{card_id}")
async def get_card_endpoint(deck_id: UUID, card_id: UUID, user_id: UserId) -> FlashcardCardResponse:
    """Get a single card by ID."""
    return await get_card(deck_id, card_id, user_id=user_id)
