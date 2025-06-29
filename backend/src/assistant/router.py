import os
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from src.ai.constants import rag_config
from src.ai.rag.reprocess_books import reprocess_book

from .schemas import ChatRequest
from .service import enhanced_assistant_service, get_available_models, streaming_enhanced_assistant_service


router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


@router.get("/models")
async def get_models() -> dict:
    """Get available AI models for the assistant."""
    return await get_available_models()


@router.get("/debug/config")
async def debug_config() -> dict:
    """Debug endpoint to check configuration."""
    try:

        return {
            "env_var": os.getenv("RAG_EMBEDDING_OUTPUT_DIM"),
            "rag_config_dim": rag_config.embedding_dim,
            "rag_config_model": rag_config.embedding_model,
        }
    except Exception as e:
        return {"error": str(e)}


@router.post("/chat", response_model=None)
async def chat_endpoint(request: ChatRequest) -> StreamingResponse | JSONResponse:
    """Send a message to the AI assistant with enhanced RAG capabilities."""
    if request.stream:
        return StreamingResponse(
            streaming_enhanced_assistant_service.chat_with_assistant_streaming_enhanced(request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
            },
        )

    # Use enhanced Phase 3 service for non-streaming
    return await enhanced_assistant_service.chat_with_assistant_enhanced(request)


@router.post("/reprocess-book/{book_id}")
async def reprocess_book_endpoint(book_id: UUID) -> dict:
    """Reprocess a book's chunks with updated metadata."""
    try:
        result = await reprocess_book(book_id)

        if result["status"] == "error":
            raise HTTPException(status_code=404, detail=result["message"])

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
