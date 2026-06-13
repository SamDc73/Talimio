"""RAG system API router with dependency injection."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from src.ai.rag.schemas import SearchRequest, SearchResponse
from src.ai.rag.service import RAGService
from src.auth import CurrentAuth


# RAG owns the course-scoped search route. Ingestion happens only through
# books (POST /api/v1/books); courses reference books via course_attachments.
router = APIRouter(prefix="/api/v1", tags=["rag"])


def get_rag_service() -> RAGService:
    """Dependency to get RAG service instance."""
    return RAGService()


@router.post("/courses/{course_id}/search", response_model=SearchResponse)
async def search_documents(
    course_id: uuid.UUID,
    search_request: SearchRequest,
    auth: CurrentAuth,
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
) -> SearchResponse:
    """Search attached book sources within a course using RAG."""
    results = await rag_service.search_documents(
        user_id=auth.user_id,
        course_id=course_id,
        query=search_request.query,
        top_k=search_request.top_k,
    )
    return SearchResponse(results=results, total=len(results))
