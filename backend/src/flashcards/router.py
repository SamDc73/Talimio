from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from src.auth.dependencies import EffectiveUserId

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
    get_deck,
    get_deck_cards,
    get_decks,
    get_study_session,
    review_card,
    update_card,
    update_deck,
)


router = APIRouter(prefix="/api/v1/flashcards", tags=["flashcards"])


# Deck endpoints
@router.get("")
async def list_decks(
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    per_page: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    user_id: EffectiveUserId = None,
) -> DeckListResponse:
    """List all flashcard decks."""
    # Note: user_id is available for future multi-user support
    # Currently using DEFAULT_USER_ID in service layer
    return await get_decks(page=page, per_page=per_page, user_id=user_id)


@router.get("/{deck_id}")
async def get_deck_endpoint(deck_id: UUID, user_id: EffectiveUserId = None) -> FlashcardDeckResponse:
    """Get deck details."""
    return await get_deck(deck_id, user_id=user_id)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_deck_endpoint(deck_data: FlashcardDeckCreate, user_id: EffectiveUserId = None) -> FlashcardDeckResponse:
    """Create a new deck."""
    return await create_deck(deck_data, user_id=user_id)


@router.put("/{deck_id}")
async def update_deck_endpoint(deck_id: UUID, deck_data: FlashcardDeckUpdate, user_id: EffectiveUserId = None) -> FlashcardDeckResponse:
    """Update deck details."""
    return await update_deck(deck_id, deck_data, user_id=user_id)


# Card endpoints
@router.get("/{deck_id}/cards")
async def get_deck_cards_endpoint(
    deck_id: UUID,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    per_page: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    user_id: EffectiveUserId = None,
) -> CardListResponse:
    """Get all cards in a deck."""
    return await get_deck_cards(deck_id, page=page, per_page=per_page, user_id=user_id)


@router.post("/{deck_id}/cards", status_code=status.HTTP_201_CREATED)
async def create_card_endpoint(deck_id: UUID, card_data: FlashcardCardCreate, user_id: EffectiveUserId = None) -> FlashcardCardResponse:
    """Add a card to a deck."""
    # Note: user_id is available for future multi-user support
    return await create_card(deck_id, card_data, user_id=user_id)


@router.put("/{deck_id}/cards/{card_id}")
async def update_card_endpoint(
    deck_id: UUID,
    card_id: UUID,
    card_data: FlashcardCardUpdate,
    user_id: EffectiveUserId = None,
) -> FlashcardCardResponse:
    """Update a card."""
    return await update_card(deck_id, card_id, card_data, user_id=user_id)


# Review endpoints
@router.put("/{deck_id}/cards/{card_id}/review")
async def review_card_endpoint(
    deck_id: UUID,
    card_id: UUID,
    review_data: FlashcardReviewRequest,
    user_id: EffectiveUserId = None,
) -> FlashcardReviewResponse:
    """Submit a card review (for spaced repetition)."""
    return await review_card(deck_id, card_id, review_data, user_id=user_id)


@router.get("/{deck_id}/study")
async def get_study_session_endpoint(
    deck_id: UUID,
    limit: Annotated[int, Query(ge=1, le=100, description="Maximum cards to return")] = 20,
    user_id: EffectiveUserId = None,
) -> StudySessionResponse:
    """Get cards due for review in a deck."""
    return await get_study_session(deck_id, limit=limit, user_id=user_id)
