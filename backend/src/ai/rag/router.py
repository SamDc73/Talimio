"""RAG system API router with dependency injection."""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.rag.schemas import (
    DefaultResponse,
    DocumentList,
    DocumentResponse,
    SearchRequest,
    SearchResponse,
)
from src.ai.rag.service import RAGService
from src.auth import UserId
from src.database.session import get_db_session


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


async def validate_course_access(
    course_id: uuid.UUID,
    user_id: UserId,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Validate user has access to course."""
    # Check if course exists and user owns it
    result = await session.execute(
        text("SELECT id FROM roadmaps WHERE id = :course_id AND user_id = :user_id"),
        {"course_id": str(course_id), "user_id": str(user_id)},
    )
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Course not found or access denied")


@router.post("/courses/{course_id}/documents")
async def upload_document(
    course_id: uuid.UUID,
    document_type: Annotated[str, Form()],
    title: Annotated[str, Form()],
    user_id: UserId,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
    url: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> DocumentResponse:
    """Upload a document to a course."""
    # Validate course access first
    await validate_course_access(course_id, user_id, session)

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
            session=session,
            user_id=user_id,  # Pass user_id to service
            course_id=course_id,
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


@router.get("/courses/{course_id}/documents")
async def list_documents(
    course_id: uuid.UUID,
    user_id: UserId,
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    skip: int = 0,
    limit: int = 20,
) -> DocumentList:
    """List documents for a course - with proper error handling."""
    # Validate course access first
    await validate_course_access(course_id, user_id, session)

    try:
        documents = await rag_service.get_documents(
            session=session, user_id=user_id, course_id=course_id, skip=skip, limit=limit
        )

        # Get total count
        total = await rag_service.count_documents(session=session, user_id=user_id, course_id=course_id)

        return DocumentList(documents=documents, total=total, page=skip // limit + 1, size=limit)

    except Exception:
        # Log but don't crash - return empty list
        logger.exception("Error listing documents for course %s", course_id)
        return DocumentList(documents=[], total=0, page=1, size=limit)


@router.post("/courses/{course_id}/search")
async def search_documents(
    course_id: uuid.UUID,
    search_request: SearchRequest,
    user_id: UserId,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
) -> SearchResponse:
    """Search documents within a course using RAG."""
    # Validate course access first
    await validate_course_access(course_id, user_id, session)

    try:
        results = await rag_service.search_documents(
            session=session, user_id=user_id, course_id=course_id,
            query=search_request.query, top_k=search_request.top_k
        )

        return SearchResponse(results=results, total=len(results))

    except Exception:
        logger.exception("Error searching documents")
        return SearchResponse(results=[], total=0)


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    user_id: UserId,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
) -> DefaultResponse:
    """Delete a document."""
    try:
        # Validate user owns the document and delete it
        await rag_service.delete_document(session, user_id, document_id)
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
    user_id: UserId,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DocumentResponse:
    """Get document details."""
    try:
        # Get document and verify user owns it via course
        result = await session.execute(
            text("""
                SELECT rd.* FROM roadmap_documents rd
                JOIN roadmaps r ON rd.roadmap_id = r.id
                WHERE rd.id = :doc_id AND r.user_id = :user_id
            """),
            {"doc_id": document_id, "user_id": str(user_id)}
        )
        row = result.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Document not found or access denied")

        return DocumentResponse.model_validate(row._asdict())

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error getting document")
        raise HTTPException(status_code=500, detail="Failed to get document") from e


# URL extraction endpoint removed - MVP only supports file uploads
