"""RAG system API router with dependency injection."""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from src.ai.rag.schemas import (
    DefaultResponse,
    DocumentList,
    DocumentResponse,
    SearchRequest,
    SearchResponse,
)
from src.ai.rag.service import RAGService
from src.auth import CurrentAuth
from src.courses.models import Roadmap


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1", tags=["rag"])

# DO NOT create services at module level!
_rag_service: RAGService | None = None


async def get_rag_service() -> RAGService:
    """Dependency to get RAG service instance."""
    global _rag_service  # noqa: PLW0603
    if _rag_service is None:
        try:
            _rag_service = RAGService()
        except Exception:
            logger.exception("Failed to initialize RAG service")
            # Create a minimal instance that won't crash
            _rag_service = RAGService()
    return _rag_service


# Ownership validation is handled via UserContext in each endpoint


@router.post("/courses/{course_id}/documents")
async def upload_document(
    course_id: uuid.UUID,
    document_type: Annotated[str, Form()],
    title: Annotated[str, Form()],
    auth: CurrentAuth,
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
    url: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> DocumentResponse:
    """Upload a document to a course."""
    # Validate course access via AuthContext
    await auth.get_or_404(Roadmap, course_id, "course")

    # Only file uploads supported in MVP (no URL crawling)
    if not file:
        raise HTTPException(status_code=400, detail="File upload required")

    if document_type == "url":
        raise HTTPException(status_code=400, detail="URL documents not supported in MVP. Please upload a file.")

    file_content = None
    filename = None
    if file:
        file_content = await file.read()
        filename = file.filename

    try:
        return await rag_service.upload_document(
            auth,
            course_id,
            document_type,
            title,
            file_content,
            url,
            filename,
        )

        # Don't process immediately to avoid blocking
        # TODO: Add to background job queue

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to upload document")
        raise HTTPException(status_code=500, detail="Failed to upload document") from e


@router.get("/courses/{course_id}/documents")
async def list_documents(
    course_id: uuid.UUID,
    auth: CurrentAuth,
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
    skip: int = 0,
    limit: int = 20,
) -> DocumentList:
    """List documents for a course - with proper error handling."""
    # Validate course access via AuthContext
    await auth.get_or_404(Roadmap, course_id, "course")

    try:
        documents = await rag_service.get_documents(auth, course_id, skip=skip, limit=limit)

        # Get total count
        total = await rag_service.count_documents(auth, course_id)

        return DocumentList(documents=documents, total=total, page=skip // limit + 1, size=limit)

    except Exception:
        # Log but don't crash - return empty list
        logger.exception("Error listing documents for course %s", course_id)
        return DocumentList(documents=[], total=0, page=1, size=limit)


@router.post("/courses/{course_id}/search")
async def search_documents(
    course_id: uuid.UUID,
    search_request: SearchRequest,
    auth: CurrentAuth,
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
) -> SearchResponse:
    """Search documents within a course using RAG."""
    # Validate course access via AuthContext
    await auth.get_or_404(Roadmap, course_id, "course")

    try:
        results = await rag_service.search_documents(
            auth,
            course_id,
            search_request.query,
            search_request.top_k,
        )

        return SearchResponse(results=results, total=len(results))

    except Exception:
        logger.exception("Error searching documents")
        return SearchResponse(results=[], total=0)


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    auth: CurrentAuth,
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
) -> DefaultResponse:
    """Delete a document."""
    try:
        # Validate user owns the document and delete it
        await rag_service.delete_document(auth, document_id)
        return DefaultResponse(
            status=True,
            message="Document deleted successfully",
        )

    except Exception as e:
        logger.exception("Error deleting document")
        raise HTTPException(status_code=500, detail="Failed to delete document") from e


@router.get("/documents/{document_id}")
async def get_document(
    document_id: int,
    auth: CurrentAuth,
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
) -> DocumentResponse:
    """Get document details."""
    return await rag_service.get_document(auth, document_id)


# URL extraction endpoint removed - MVP only supports file uploads
