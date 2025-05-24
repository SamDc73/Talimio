from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class FlashcardDeck(Base):
    """Model for flashcard decks."""

    __tablename__ = "flashcard_decks"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # For future user support
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    is_public: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    # Relationships
    cards: Mapped[list["FlashcardCard"]] = relationship(
        "FlashcardCard", back_populates="deck", cascade="all, delete-orphan",
    )


class FlashcardCard(Base):
    """Model for individual flashcards."""

    __tablename__ = "flashcard_cards"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    deck_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("flashcard_decks.id"), nullable=False, index=True,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    difficulty: Mapped[str] = mapped_column(String(10), default="medium")  # easy, medium, hard

    # FSRS algorithm fields
    due: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    stability: Mapped[float] = mapped_column(Float, default=2.0)
    difficulty_score: Mapped[float] = mapped_column(Float, default=5.0)  # FSRS difficulty (not card difficulty)
    elapsed_days: Mapped[int] = mapped_column(Integer, default=0)
    scheduled_days: Mapped[int] = mapped_column(Integer, default=0)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[int] = mapped_column(Integer, default=0)  # 0=New, 1=Learning, 2=Review, 3=Relearning
    last_review: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    # Relationships
    deck: Mapped["FlashcardDeck"] = relationship("FlashcardDeck", back_populates="cards")
    reviews: Mapped[list["FlashcardReview"]] = relationship(
        "FlashcardReview", back_populates="card", cascade="all, delete-orphan",
    )


class FlashcardReview(Base):
    """Model for tracking flashcard reviews."""

    __tablename__ = "flashcard_reviews"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    card_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("flashcard_cards.id"), nullable=False, index=True,
    )
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1=Again, 2=Hard, 3=Good, 4=Easy
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    card: Mapped["FlashcardCard"] = relationship("FlashcardCard", back_populates="reviews")
