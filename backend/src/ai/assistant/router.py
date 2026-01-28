"""Assistant API router - simple chat endpoint."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.auth import CurrentAuth
from src.config.settings import get_settings

from .schemas import ChatRequest
from .service import chat_with_assistant


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


def _clean_model_id(model_id: str) -> str:
    """Remove all provider prefixes from model ID."""
    # Handle nested prefixes like "openrouter/openai/gpt-4"
    parts = model_id.split("/")
    return parts[-1]  # Always return just the model name


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


@router.get("/models")
async def get_models() -> dict[str, list[dict[str, Any]]]:
    """Return list of available assistant models.

    Minimal payload for UI model picker:
    - id: full model identifier (e.g., "openrouter/openai/gpt-4o")
    - displayName: cleaned model name without provider prefixes (e.g., "gpt-4o")
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
                "displayName": _clean_model_id(model_id),
                "isDefault": i == 0,
            })
            seen.add(model_id)

        return {"models": models}

    except Exception as e:
        logger.exception("Failed to fetch assistant models")
        raise HTTPException(status_code=500, detail="Failed to fetch assistant models") from e
