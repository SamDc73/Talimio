from fastapi import APIRouter, status

from .schemas import (
    ChatRequest,
    ChatResponse,
    GenerateCourseRequest,
    GenerateCourseResponse,
    GenerateFlashcardsRequest,
    GenerateFlashcardsResponse,
)
from .service import chat_with_assistant, generate_course, generate_flashcards


router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


@router.post("/chat")
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """Send a message to the AI assistant."""
    return await chat_with_assistant(request)


@router.post("/generate-course", status_code=status.HTTP_201_CREATED)
async def generate_course_endpoint(request: GenerateCourseRequest) -> GenerateCourseResponse:
    """Generate a course on a topic."""
    return await generate_course(request)


@router.post("/generate-flashcards", status_code=status.HTTP_201_CREATED)
async def generate_flashcards_endpoint(request: GenerateFlashcardsRequest) -> GenerateFlashcardsResponse:
    """Generate flashcards from content."""
    return await generate_flashcards(request)
