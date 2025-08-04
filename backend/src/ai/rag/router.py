"""RAG system API router - FIXED VERSION."""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.rag.ingest import URLIngestor
from src.ai.rag.schemas import (
    DocumentList,
    DocumentResponse,
    SearchRequest,
    SearchResponse,
)
from src.ai.rag.service import RAGService
from src.database.session import get_db_session


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1", tags=["rag"])

# DO NOT create services at module level!
_rag_service: RAGService | None = None
_url_ingestor: URLIngestor | None = None


def get_rag_service() -> RAGService:
    """Get or create RAG service instance - truly lazy."""
    global _rag_service  # noqa: PLW0603
    if _rag_service is None:
        try:
            _rag_service = RAGService()
        except Exception:
            logger.exception("Failed to initialize RAG service")
            # Create a minimal instance that won't crash
            _rag_service = RAGService()
    return _rag_service


def get_url_ingestor() -> URLIngestor:
    """Get or create URLIngestor instance."""
    global _url_ingestor  # noqa: PLW0603
    if _url_ingestor is None:
        try:
            _url_ingestor = URLIngestor()
        except Exception:
            logger.exception("Failed to initialize URL ingestor")
            # Return None and handle in endpoint
    return _url_ingestor


@router.post("/roadmaps/{roadmap_id}/documents")
async def upload_document(
    roadmap_id: uuid.UUID,
    document_type: Annotated[str, Form()],
    title: Annotated[str, Form()],
    url: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> DocumentResponse:
    """Upload a document to a roadmap."""
    # For file uploads, document_type might be generic "file" or specific like "pdf"
    if document_type != "url" and not file:
        raise HTTPException(status_code=400, detail="File required for file uploads")

    if document_type == "url" and not url:
        raise HTTPException(status_code=400, detail="URL required for URL documents")

    file_content = None
    filename = None
    if file:
        file_content = await file.read()
        filename = file.filename

    try:
        rag_service = get_rag_service()
        return await rag_service.upload_document(
            session=session,
            roadmap_id=roadmap_id,
            document_type=document_type,
            title=title,
            file_content=file_content,
            url=url,
            filename=filename,
        )

        # Don't process immediately to avoid blocking
        # TODO: Add to background job queue

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to upload document")
        raise HTTPException(status_code=500, detail="Failed to upload document") from e


@router.get("/roadmaps/{roadmap_id}/documents")
async def list_documents(
    roadmap_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> DocumentList:
    """List documents for a roadmap - with proper error handling."""
    try:
        rag_service = get_rag_service()
        if not rag_service:
            # Return empty list if service failed to initialize
            logger.error("RAG service not available")
            return DocumentList(documents=[], total=0, page=1, size=limit)

        documents = await rag_service.get_documents(session=session, roadmap_id=roadmap_id, skip=skip, limit=limit)

        # Get total count
        total = await rag_service.count_documents(session=session, roadmap_id=roadmap_id)

        return DocumentList(documents=documents, total=total, page=skip // limit + 1, size=limit)

    except Exception:
        # Log but don't crash - return empty list
        logger.exception("Error listing documents for roadmap %s", roadmap_id)
        return DocumentList(documents=[], total=0, page=1, size=limit)


@router.post("/roadmaps/{roadmap_id}/search")
async def search_documents(
    roadmap_id: uuid.UUID,
    search_request: SearchRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> SearchResponse:
    """Search documents within a roadmap using RAG."""
    try:
        rag_service = get_rag_service()
        if not rag_service:
            return SearchResponse(results=[], total=0)

        results = await rag_service.search_documents(
            session=session, roadmap_id=roadmap_id, query=search_request.query, top_k=search_request.top_k
        )

        return SearchResponse(results=results, total=len(results))

    except Exception:
        logger.exception("Error searching documents")
        return SearchResponse(results=[], total=0)


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> dict:
    """Delete a document."""
    try:
        rag_service = get_rag_service()
        await rag_service.delete_document(session, document_id)
        return {"message": "Document deleted successfully"}

    except Exception as e:
        logger.exception("Error deleting document")
        raise HTTPException(status_code=500, detail="Failed to delete document") from e


@router.get("/documents/{document_id}")
async def get_document(
    document_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> DocumentResponse:
    """Get document details."""
    try:
        result = await session.execute(
            text("SELECT * FROM roadmap_documents WHERE id = :doc_id"), {"doc_id": document_id}
        )
        row = result.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Document not found")

        return DocumentResponse.model_validate(row._asdict())

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting document")
        raise HTTPException(status_code=500, detail="Failed to get document") from e


@router.post("/extract-title")
async def extract_title_from_url(url: Annotated[str, Form()]) -> dict:
    """Extract title from a given URL."""
    try:
        url_ingestor = get_url_ingestor()
        if not url_ingestor:
            return {"title": "Untitled Document", "error": "URL ingestor not available"}

        title = url_ingestor.extract_title_from_url(url)
        return {"title": title}
    except Exception as e:
        logger.exception("Error extracting title")
        return {"title": "Untitled Document", "error": str(e)}
