from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from .schemas import ChatRequest, ChatResponse
from .service import chat_with_assistant, chat_with_assistant_streaming, get_available_models


router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


@router.get("/models")
async def get_models():
    """Get available AI models for the assistant."""
    return await get_available_models()


@router.post("/chat")
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """Send a message to the AI assistant."""
    if request.stream:
        return StreamingResponse(
            chat_with_assistant_streaming(request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
            }
        )
    return await chat_with_assistant(request)
