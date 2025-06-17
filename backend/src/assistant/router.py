from fastapi import APIRouter

from .schemas import ChatRequest, ChatResponse
from .service import chat_with_assistant


router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


@router.post("/chat")
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """Send a message to the AI assistant."""
    return await chat_with_assistant(request)
