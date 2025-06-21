"""RAG system API router."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.rag.schemas import (
    DocumentList,
    DocumentResponse,
    SearchRequest,
    SearchResponse,
)
from src.ai.rag.service import RAGService
from src.database.session import get_db_session


router = APIRouter(prefix="/api/v1", tags=["rag"])
rag_service = RAGService()


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
    if document_type == "pdf" and not file:
        raise HTTPException(status_code=400, detail="PDF file required for PDF documents")

    if document_type == "url" and not url:
        raise HTTPException(status_code=400, detail="URL required for URL documents")

    file_content = None
    if file:
        file_content = await file.read()

    try:
        document = await rag_service.upload_document(
            session=session,
            roadmap_id=roadmap_id,
            document_type=document_type,
            title=title,
            file_content=file_content,
            url=url,
        )

        # TODO: Add to background job queue for processing
        # For now, process immediately (blocking)
        await rag_service.process_document(session, document.id)

        return document

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/roadmaps/{roadmap_id}/documents")
async def list_documents(
    roadmap_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> DocumentList:
    """List documents for a roadmap."""
    try:
        documents = await rag_service.get_documents(session=session, roadmap_id=roadmap_id, skip=skip, limit=limit)

        # Get total count
        total = len(documents)  # TODO: Implement proper count query

        return DocumentList(documents=documents, total=total, page=skip // limit + 1, size=limit)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/roadmaps/{roadmap_id}/search")
async def search_documents(
    roadmap_id: uuid.UUID,
    search_request: SearchRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> SearchResponse:
    """Search documents within a roadmap using RAG."""
    try:
        results = await rag_service.search_documents(
            session=session, roadmap_id=roadmap_id, query=search_request.query, top_k=search_request.top_k
        )

        return SearchResponse(results=results, total=len(results))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> dict:
    """Delete a document."""
    try:
        await rag_service.delete_document(session, document_id)
        return {"message": "Document deleted successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/documents/{document_id}")
async def get_document(
    document_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> DocumentResponse:
    """Get document details."""
    try:
        from sqlalchemy import text

        result = await session.execute(
            text("SELECT * FROM roadmap_documents WHERE id = :doc_id"), {"doc_id": document_id}
        )
        row = result.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Document not found")

        return DocumentResponse.model_validate(dict(row))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
