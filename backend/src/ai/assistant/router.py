"""Assistant API router - simple chat endpoint."""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.auth import CurrentAuth

from .schemas import ChatRequest
from .service import chat_with_assistant


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


@router.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    auth: CurrentAuth,
) -> StreamingResponse:
    """Stream chat responses from the AI assistant."""
    try:
        return StreamingResponse(
            chat_with_assistant(request, user_id=auth.user_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
    except Exception as e:
        logger.exception("Chat endpoint failed")
        raise HTTPException(status_code=500, detail="Chat service temporarily unavailable") from e
