from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.ai.constants import rag_config
from src.auth import CurrentAuth
from src.config import env

from .schemas import (
    BatchCitationRequest,
    BatchCitationResponse,
    ChatRequest,
    CitationRequest,
    CitationResponse,
)
from .service import assistant_service, get_available_models


# Temporary implementation until reprocess_books module is available
async def reprocess_book(_book_id: UUID) -> dict:
    """Temporary implementation for reprocess_book."""
    return {"status": "error", "message": "Reprocess functionality not yet implemented"}


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
            "env_var": env("RAG_EMBEDDING_OUTPUT_DIM"),
            "rag_config_dim": rag_config.embedding_dim,
            "rag_config_model": rag_config.embedding_model,
        }
    except Exception as e:
        return {"error": str(e)}


@router.post("/chat", response_model=None)
async def chat_endpoint(
    request: ChatRequest,
    auth: CurrentAuth,
) -> StreamingResponse:
    """Send a message to the AI assistant with enhanced RAG capabilities (always streaming)."""
    # Override the user_id from the request with the authenticated user_id
    if auth and getattr(auth, "user_id", None):
        request.user_id = auth.user_id

    # Always use streaming
    return StreamingResponse(
        assistant_service.chat_with_assistant(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


@router.post("/reprocess-book/{book_id}")
async def reprocess_book_endpoint(book_id: UUID, auth: CurrentAuth) -> dict:
    """Reprocess a book's chunks with updated metadata."""
    try:
        # TODO: Verify book ownership before reprocessing
        result = await reprocess_book(book_id)

        if result["status"] == "error":
            raise HTTPException(status_code=404, detail=result["message"])

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/citations")
async def find_citations(request: CitationRequest, auth: CurrentAuth) -> CitationResponse:
    """Find text locations in a book for citation highlighting."""
    try:
        # TODO: Verify book ownership
        # Get citation service
        citations = await assistant_service.find_book_citations(
            book_id=request.book_id,
            _response_text=request.response_text,
            _similarity_threshold=request.similarity_threshold,
        )

        return CitationResponse(citations=citations)
    except ValueError as e:
        if "Book not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e)) from e
        if "not been processed" in str(e):
            raise HTTPException(status_code=400, detail=str(e)) from e
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to find citations: {e!s}") from e


@router.post("/citations/batch")
async def find_batch_citations(request: BatchCitationRequest, auth: CurrentAuth) -> BatchCitationResponse:
    """Find text locations for multiple response texts in batch."""
    try:
        # TODO: Verify book ownership
        all_citations = []

        for response_text in request.response_texts:
            citations = await assistant_service.find_book_citations(
                book_id=request.book_id,
                _response_text=response_text,
                _similarity_threshold=request.similarity_threshold,
            )
            all_citations.append(citations)

        return BatchCitationResponse(citations=all_citations)
    except ValueError as e:
        if "Book not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e)) from e
        if "not been processed" in str(e):
            raise HTTPException(status_code=400, detail=str(e)) from e
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to find batch citations: {e!s}") from e
