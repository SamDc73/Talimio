"""Assistant API router - simple chat endpoint."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.auth import CurrentAuth
from src.config.settings import get_settings

from . import service as assistant_service
from .schemas import ChatRequest


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


@router.post("/chat")
async def assistant_chat(
    request: ChatRequest,
    auth: CurrentAuth,
) -> StreamingResponse:
    """Stream chat responses from the AI assistant."""
    try:
        return StreamingResponse(
            assistant_service.assistant_chat(request, user_id=auth.user_id, session=auth.session),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "x-vercel-ai-ui-message-stream": "v1",
            },
        )
    except Exception as e:
        logger.exception("Chat endpoint failed")
        raise HTTPException(status_code=500, detail="Chat service temporarily unavailable") from e


@router.get("/models")
async def get_models() -> dict[str, list[dict[str, Any]]]:
    """Return list of available assistant models.

    Minimal payload for UI model picker:
    - id: full model identifier (e.g., "gpt-5-nano")
    - isDefault: whether this is the primary model
    """
    try:
        # Ensure settings/env are loaded
        settings = get_settings()

        primary = settings.primary_llm_model
        available_raw = settings.AVAILABLE_MODELS
        available = [m.strip() for m in available_raw.split(",") if m.strip()] if available_raw else []

        # Build ordered unique list with primary first
        ordered = [primary, *available]
        seen: set[str] = set()
        models: list[dict[str, Any]] = []

        for i, model_id in enumerate(ordered):
            if model_id in seen:
                continue
            models.append({
                "id": model_id,
                "isDefault": i == 0,
            })
            seen.add(model_id)

        return {"models": models}

    except Exception as e:
        logger.exception("Failed to fetch assistant models")
        raise HTTPException(status_code=500, detail="Failed to fetch assistant models") from e
