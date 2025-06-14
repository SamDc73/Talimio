from uuid import UUID

from pydantic import BaseModel


class ChatMessage(BaseModel):
    """Schema for a chat message."""

    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """Request schema for chat endpoint."""

    message: str
    conversation_history: list[ChatMessage] = []
    user_id: str | None = None


class ChatResponse(BaseModel):
    """Response schema for chat endpoint."""

    response: str
    conversation_id: UUID | None = None


class GenerateCourseRequest(BaseModel):
    """Request schema for generating a course."""

    topic: str
    skill_level: str = "beginner"
    description: str | None = None
    duration_weeks: int = 4
    user_id: str | None = None


class CourseModule(BaseModel):
    """Schema for a course module."""

    title: str
    description: str
    content: str
    order: int
    estimated_hours: int


class GenerateCourseResponse(BaseModel):
    """Response schema for course generation."""

    course_id: UUID
    title: str
    description: str
    skill_level: str
    modules: list[CourseModule]
    total_estimated_hours: int


class GenerateFlashcardsRequest(BaseModel):
    """Request schema for generating flashcards."""

    content: str
    topic: str | None = None
    num_cards: int = 10
    user_id: str | None = None


class FlashcardItem(BaseModel):
    """Schema for a flashcard item."""

    question: str
    answer: str
    difficulty: str = "medium"
    tags: list[str] = []


class GenerateFlashcardsResponse(BaseModel):
    """Response schema for flashcard generation."""

    flashcards: list[FlashcardItem]
    topic: str
    total_cards: int
