from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FlashcardDeckBase(BaseModel):
    """Base schema for flashcard deck."""

    name: str = Field(..., max_length=200)
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    is_public: bool = False


class FlashcardDeckCreate(FlashcardDeckBase):
    """Schema for creating flashcard deck."""


class FlashcardDeckUpdate(BaseModel):
    """Schema for updating flashcard deck."""

    name: str | None = Field(None, max_length=200)
    description: str | None = None
    tags: list[str] | None = None
    is_public: bool | None = None


class FlashcardDeckResponse(FlashcardDeckBase):
    """Schema for flashcard deck response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: str
    created_at: datetime
    updated_at: datetime
    card_count: int = 0  # Will be populated by service

    @property
    def tags_list(self) -> list[str]:
        """Convert tags JSON string to list."""
        if isinstance(self.tags, str):
            import json

            try:
                return json.loads(self.tags)
            except (json.JSONDecodeError, TypeError):
                return []
        return self.tags or []


class FlashcardCardBase(BaseModel):
    """Base schema for flashcard."""

    question: str
    answer: str
    hint: str | None = None
    tags: list[str] = Field(default_factory=list)
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")


class FlashcardCardCreate(FlashcardCardBase):
    """Schema for creating flashcard."""


class FlashcardCardUpdate(BaseModel):
    """Schema for updating flashcard."""

    question: str | None = None
    answer: str | None = None
    hint: str | None = None
    tags: list[str] | None = None
    difficulty: str | None = Field(None, pattern="^(easy|medium|hard)$")


class FlashcardCardResponse(FlashcardCardBase):
    """Schema for flashcard response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    deck_id: UUID
    due: datetime
    stability: float
    difficulty_score: float
    reps: int
    lapses: int
    state: int
    last_review: datetime | None
    created_at: datetime
    updated_at: datetime

    @property
    def tags_list(self) -> list[str]:
        """Convert tags JSON string to list."""
        if isinstance(self.tags, str):
            import json

            try:
                return json.loads(self.tags)
            except (json.JSONDecodeError, TypeError):
                return []
        return self.tags or []

    @property
    def state_name(self) -> str:
        """Get human-readable state name."""
        states = {0: "new", 1: "learning", 2: "review", 3: "relearning"}
        return states.get(self.state, "unknown")


class FlashcardReviewRequest(BaseModel):
    """Schema for submitting flashcard review."""

    rating: int = Field(..., ge=1, le=4, description="1=Again, 2=Hard, 3=Good, 4=Easy")
    response_time_ms: int | None = Field(None, ge=0, description="Response time in milliseconds")


class FlashcardReviewResponse(BaseModel):
    """Schema for flashcard review response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    card_id: UUID
    user_id: str
    rating: int
    response_time_ms: int | None
    reviewed_at: datetime
    next_review_info: dict = Field(default_factory=dict)  # FSRS scheduling info


class DeckListResponse(BaseModel):
    """Schema for deck list response."""

    decks: list[FlashcardDeckResponse]
    total: int
    page: int
    per_page: int


class CardListResponse(BaseModel):
    """Schema for card list response."""

    cards: list[FlashcardCardResponse]
    total: int
    page: int
    per_page: int


class StudySessionResponse(BaseModel):
    """Schema for study session response."""

    cards_due: list[FlashcardCardResponse]
    total_due: int
    deck_id: UUID
    session_started_at: datetime
