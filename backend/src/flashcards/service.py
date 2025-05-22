import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from fsrs import FSRS, Card, Rating
from sqlalchemy import func, select

from src.database.session import async_session_maker
from src.flashcards.models import FlashcardCard, FlashcardDeck, FlashcardReview
from src.flashcards.schemas import (
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


DEFAULT_USER_ID = "default_user"  # For now, use default user


async def create_deck(deck_data: FlashcardDeckCreate) -> FlashcardDeckResponse:
    """
    Create a new flashcard deck.

    Args:
        deck_data: Deck creation data

    Returns
    -------
        FlashcardDeckResponse: Created deck data

    Raises
    ------
        HTTPException: If creation fails
    """
    try:
        async with async_session_maker() as session:
            deck = FlashcardDeck(
                name=deck_data.name,
                description=deck_data.description,
                user_id=DEFAULT_USER_ID,
                tags=json.dumps(deck_data.tags) if deck_data.tags else None,
                is_public=deck_data.is_public,
            )

            session.add(deck)
            await session.commit()
            await session.refresh(deck)

            response = FlashcardDeckResponse.model_validate(deck)
            response.card_count = 0
            return response

    except Exception as e:
        logging.exception("Error creating flashcard deck")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create deck: {e!s}",
        ) from e


async def get_decks(page: int = 1, per_page: int = 20) -> DeckListResponse:
    """
    Get list of flashcard decks with pagination.

    Args:
        page: Page number (1-based)
        per_page: Number of decks per page

    Returns
    -------
        DeckListResponse: List of decks with pagination info

    Raises
    ------
        HTTPException: If retrieval fails
    """
    try:
        async with async_session_maker() as session:
            # Get total count
            count_query = select(func.count(FlashcardDeck.id)).where(
                FlashcardDeck.user_id == DEFAULT_USER_ID,
            )
            total_result = await session.execute(count_query)
            total = total_result.scalar() or 0

            # Get paginated decks with card counts
            offset = (page - 1) * per_page
            query = (
                select(FlashcardDeck, func.count(FlashcardCard.id).label("card_count"))
                .outerjoin(FlashcardCard)
                .where(FlashcardDeck.user_id == DEFAULT_USER_ID)
                .group_by(FlashcardDeck.id)
                .offset(offset)
                .limit(per_page)
            )
            result = await session.execute(query)
            rows = result.all()

            deck_responses = []
            for deck, card_count in rows:
                deck_response = FlashcardDeckResponse.model_validate(deck)
                deck_response.card_count = card_count
                deck_responses.append(deck_response)

            return DeckListResponse(
                decks=deck_responses,
                total=total,
                page=page,
                per_page=per_page,
            )

    except Exception as e:
        logging.exception("Error getting flashcard decks")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get decks: {e!s}",
        ) from e


async def get_deck(deck_id: UUID) -> FlashcardDeckResponse:
    """
    Get a flashcard deck by ID.

    Args:
        deck_id: Deck ID

    Returns
    -------
        FlashcardDeckResponse: Deck data

    Raises
    ------
        HTTPException: If deck not found or retrieval fails
    """
    try:
        async with async_session_maker() as session:
            query = select(FlashcardDeck).where(
                FlashcardDeck.id == deck_id,
                FlashcardDeck.user_id == DEFAULT_USER_ID,
            )
            result = await session.execute(query)
            deck = result.scalar_one_or_none()

            if not deck:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Deck {deck_id} not found",
                )

            # Get card count
            card_count_query = select(func.count(FlashcardCard.id)).where(
                FlashcardCard.deck_id == deck_id,
            )
            card_count_result = await session.execute(card_count_query)
            card_count = card_count_result.scalar() or 0

            deck_response = FlashcardDeckResponse.model_validate(deck)
            deck_response.card_count = card_count
            return deck_response

    except HTTPException:
        raise
    except Exception as e:
        logging.exception(f"Error getting deck {deck_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get deck: {e!s}",
        ) from e


async def update_deck(deck_id: UUID, deck_data: FlashcardDeckUpdate) -> FlashcardDeckResponse:
    """
    Update a flashcard deck.

    Args:
        deck_id: Deck ID
        deck_data: Updated deck data

    Returns
    -------
        FlashcardDeckResponse: Updated deck data

    Raises
    ------
        HTTPException: If deck not found or update fails
    """
    try:
        async with async_session_maker() as session:
            query = select(FlashcardDeck).where(
                FlashcardDeck.id == deck_id,
                FlashcardDeck.user_id == DEFAULT_USER_ID,
            )
            result = await session.execute(query)
            deck = result.scalar_one_or_none()

            if not deck:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Deck {deck_id} not found",
                )

            # Update fields
            update_data = deck_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                if field == "tags" and value is not None:
                    setattr(deck, field, json.dumps(value))
                else:
                    setattr(deck, field, value)

            deck.updated_at = datetime.now(timezone.utc)

            await session.commit()
            await session.refresh(deck)

            # Get card count
            card_count_query = select(func.count(FlashcardCard.id)).where(
                FlashcardCard.deck_id == deck_id,
            )
            card_count_result = await session.execute(card_count_query)
            card_count = card_count_result.scalar() or 0

            deck_response = FlashcardDeckResponse.model_validate(deck)
            deck_response.card_count = card_count
            return deck_response

    except HTTPException:
        raise
    except Exception as e:
        logging.exception(f"Error updating deck {deck_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update deck: {e!s}",
        ) from e


async def delete_deck(deck_id: UUID) -> None:
    """
    Delete a flashcard deck and all its cards.

    Args:
        deck_id: Deck ID

    Raises
    ------
        HTTPException: If deck not found or deletion fails
    """
    try:
        async with async_session_maker() as session:
            query = select(FlashcardDeck).where(
                FlashcardDeck.id == deck_id,
                FlashcardDeck.user_id == DEFAULT_USER_ID,
            )
            result = await session.execute(query)
            deck = result.scalar_one_or_none()

            if not deck:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Deck {deck_id} not found",
                )

            await session.delete(deck)
            await session.commit()

    except HTTPException:
        raise
    except Exception as e:
        logging.exception(f"Error deleting deck {deck_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete deck: {e!s}",
        ) from e


async def get_deck_cards(deck_id: UUID, page: int = 1, per_page: int = 20) -> CardListResponse:
    """
    Get all cards in a deck with pagination.

    Args:
        deck_id: Deck ID
        page: Page number (1-based)
        per_page: Number of cards per page

    Returns
    -------
        CardListResponse: List of cards with pagination info

    Raises
    ------
        HTTPException: If deck not found or retrieval fails
    """
    try:
        async with async_session_maker() as session:
            # Verify deck exists and belongs to user
            deck_query = select(FlashcardDeck).where(
                FlashcardDeck.id == deck_id,
                FlashcardDeck.user_id == DEFAULT_USER_ID,
            )
            deck_result = await session.execute(deck_query)
            deck = deck_result.scalar_one_or_none()

            if not deck:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Deck {deck_id} not found",
                )

            # Get total count
            count_query = select(func.count(FlashcardCard.id)).where(
                FlashcardCard.deck_id == deck_id,
            )
            total_result = await session.execute(count_query)
            total = total_result.scalar() or 0

            # Get paginated cards
            offset = (page - 1) * per_page
            query = select(FlashcardCard).where(
                FlashcardCard.deck_id == deck_id,
            ).offset(offset).limit(per_page)
            result = await session.execute(query)
            cards = result.scalars().all()

            card_responses = [FlashcardCardResponse.model_validate(card) for card in cards]

            return CardListResponse(
                cards=card_responses,
                total=total,
                page=page,
                per_page=per_page,
            )

    except HTTPException:
        raise
    except Exception as e:
        logging.exception(f"Error getting cards for deck {deck_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cards: {e!s}",
        ) from e


async def create_card(deck_id: UUID, card_data: FlashcardCardCreate) -> FlashcardCardResponse:
    """
    Add a card to a deck.

    Args:
        deck_id: Deck ID
        card_data: Card creation data

    Returns
    -------
        FlashcardCardResponse: Created card data

    Raises
    ------
        HTTPException: If deck not found or creation fails
    """
    try:
        async with async_session_maker() as session:
            # Verify deck exists and belongs to user
            deck_query = select(FlashcardDeck).where(
                FlashcardDeck.id == deck_id,
                FlashcardDeck.user_id == DEFAULT_USER_ID,
            )
            deck_result = await session.execute(deck_query)
            deck = deck_result.scalar_one_or_none()

            if not deck:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Deck {deck_id} not found",
                )

            # Create card with FSRS defaults
            card = FlashcardCard(
                deck_id=deck_id,
                question=card_data.question,
                answer=card_data.answer,
                hint=card_data.hint,
                tags=json.dumps(card_data.tags) if card_data.tags else None,
                difficulty=card_data.difficulty,
                # FSRS defaults for new cards
                due=datetime.now(timezone.utc),
                stability=2.0,
                difficulty_score=5.0,
                state=0,  # New
            )

            session.add(card)
            await session.commit()
            await session.refresh(card)

            return FlashcardCardResponse.model_validate(card)

    except HTTPException:
        raise
    except Exception as e:
        logging.exception(f"Error creating card in deck {deck_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create card: {e!s}",
        ) from e


async def update_card(deck_id: UUID, card_id: UUID, card_data: FlashcardCardUpdate) -> FlashcardCardResponse:
    """
    Update a card in a deck.

    Args:
        deck_id: Deck ID
        card_id: Card ID
        card_data: Updated card data

    Returns
    -------
        FlashcardCardResponse: Updated card data

    Raises
    ------
        HTTPException: If card not found or update fails
    """
    try:
        async with async_session_maker() as session:
            # Get card and verify it belongs to the specified deck
            query = select(FlashcardCard).where(
                FlashcardCard.id == card_id,
                FlashcardCard.deck_id == deck_id,
            )
            result = await session.execute(query)
            card = result.scalar_one_or_none()

            if not card:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Card {card_id} not found in deck {deck_id}",
                )

            # Update fields
            update_data = card_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                if field == "tags" and value is not None:
                    setattr(card, field, json.dumps(value))
                else:
                    setattr(card, field, value)

            card.updated_at = datetime.now(timezone.utc)

            await session.commit()
            await session.refresh(card)

            return FlashcardCardResponse.model_validate(card)

    except HTTPException:
        raise
    except Exception as e:
        logging.exception(f"Error updating card {card_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update card: {e!s}",
        ) from e


async def delete_card(deck_id: UUID, card_id: UUID) -> None:
    """
    Delete a card from a deck.

    Args:
        deck_id: Deck ID
        card_id: Card ID

    Raises
    ------
        HTTPException: If card not found or deletion fails
    """
    try:
        async with async_session_maker() as session:
            query = select(FlashcardCard).where(
                FlashcardCard.id == card_id,
                FlashcardCard.deck_id == deck_id,
            )
            result = await session.execute(query)
            card = result.scalar_one_or_none()

            if not card:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Card {card_id} not found in deck {deck_id}",
                )

            await session.delete(card)
            await session.commit()

    except HTTPException:
        raise
    except Exception as e:
        logging.exception(f"Error deleting card {card_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete card: {e!s}",
        ) from e


async def review_card(deck_id: UUID, card_id: UUID, review_data: FlashcardReviewRequest) -> FlashcardReviewResponse:
    """
    Submit a card review and update spaced repetition scheduling.

    Args:
        deck_id: Deck ID
        card_id: Card ID
        review_data: Review data with rating

    Returns
    -------
        FlashcardReviewResponse: Review response with next review info

    Raises
    ------
        HTTPException: If card not found or review fails
    """
    try:
        async with async_session_maker() as session:
            # Get card and verify it belongs to the specified deck
            query = select(FlashcardCard).where(
                FlashcardCard.id == card_id,
                FlashcardCard.deck_id == deck_id,
            )
            result = await session.execute(query)
            card = result.scalar_one_or_none()

            if not card:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Card {card_id} not found in deck {deck_id}",
                )

            # Create FSRS objects
            fsrs = FSRS()

            # Convert database card to FSRS Card
            fsrs_card = Card(
                due=card.due,
                stability=card.stability,
                difficulty=card.difficulty_score,
                elapsed_days=card.elapsed_days,
                scheduled_days=card.scheduled_days,
                reps=card.reps,
                lapses=card.lapses,
                state=card.state,
                last_review=card.last_review,
            )

            # Convert rating (1-4) to FSRS Rating enum
            rating_map = {1: Rating.Again, 2: Rating.Hard, 3: Rating.Good, 4: Rating.Easy}
            fsrs_rating = rating_map[review_data.rating]

            # Calculate next review
            scheduling_cards = fsrs.repeat(fsrs_card, card.due)
            next_card = scheduling_cards[fsrs_rating]

            # Update card with new FSRS values
            now = datetime.now(timezone.utc)
            card.due = next_card.due
            card.stability = next_card.stability
            card.difficulty_score = next_card.difficulty
            card.elapsed_days = next_card.elapsed_days
            card.scheduled_days = next_card.scheduled_days
            card.reps = next_card.reps
            card.lapses = next_card.lapses
            card.state = next_card.state
            card.last_review = now
            card.updated_at = now

            # Create review record
            review = FlashcardReview(
                card_id=card_id,
                user_id=DEFAULT_USER_ID,
                rating=review_data.rating,
                response_time_ms=review_data.response_time_ms,
                reviewed_at=now,
            )

            session.add(review)
            await session.commit()
            await session.refresh(review)

            # Prepare response with next review info
            next_review_info = {
                "next_due": next_card.due.isoformat(),
                "stability": next_card.stability,
                "difficulty": next_card.difficulty,
                "state": next_card.state,
                "scheduled_days": next_card.scheduled_days,
            }

            response = FlashcardReviewResponse.model_validate(review)
            response.next_review_info = next_review_info
            return response

    except HTTPException:
        raise
    except Exception as e:
        logging.exception(f"Error reviewing card {card_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to review card: {e!s}",
        ) from e


async def get_study_session(deck_id: UUID, limit: int = 20) -> StudySessionResponse:
    """
    Get cards due for review in a deck.

    Args:
        deck_id: Deck ID
        limit: Maximum number of cards to return

    Returns
    -------
        StudySessionResponse: Cards due for review

    Raises
    ------
        HTTPException: If deck not found or retrieval fails
    """
    try:
        async with async_session_maker() as session:
            # Verify deck exists and belongs to user
            deck_query = select(FlashcardDeck).where(
                FlashcardDeck.id == deck_id,
                FlashcardDeck.user_id == DEFAULT_USER_ID,
            )
            deck_result = await session.execute(deck_query)
            deck = deck_result.scalar_one_or_none()

            if not deck:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Deck {deck_id} not found",
                )

            # Get cards due for review
            now = datetime.now(timezone.utc)
            query = select(FlashcardCard).where(
                FlashcardCard.deck_id == deck_id,
                FlashcardCard.due <= now,
            ).limit(limit)

            result = await session.execute(query)
            cards = result.scalars().all()

            # Get total count of due cards
            count_query = select(func.count(FlashcardCard.id)).where(
                FlashcardCard.deck_id == deck_id,
                FlashcardCard.due <= now,
            )
            total_result = await session.execute(count_query)
            total_due = total_result.scalar() or 0

            card_responses = [FlashcardCardResponse.model_validate(card) for card in cards]

            return StudySessionResponse(
                cards_due=card_responses,
                total_due=total_due,
                deck_id=deck_id,
                session_started_at=now,
            )

    except HTTPException:
        raise
    except Exception as e:
        logging.exception(f"Error getting study session for deck {deck_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get study session: {e!s}",
        ) from e
