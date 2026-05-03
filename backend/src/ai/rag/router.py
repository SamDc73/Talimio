"""RAG system API router with dependency injection."""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile

from src.ai.rag.schemas import DefaultResponse, DocumentList, DocumentResponse, SearchRequest, SearchResponse
from src.ai.rag.service import RAGService
from src.auth import CurrentAuth


# RAG owns course-scoped document routes and standalone document routes.
router = APIRouter(prefix="/api/v1", tags=["rag"])


def get_rag_service() -> RAGService:
    """Dependency to get RAG service instance."""
    return RAGService()


@router.post("/courses/{course_id}/documents", response_model=DocumentResponse)
async def upload_document(
    course_id: uuid.UUID,
    document_type: Annotated[str, Form(alias="documentType", max_length=50)],
    title: Annotated[str, Form(max_length=255)],
    background_tasks: BackgroundTasks,
    auth: CurrentAuth,
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
    file: Annotated[UploadFile, File()],
) -> DocumentResponse:
    """Upload a document to a course."""
    file_content = await file.read()
    return await rag_service.upload_document(
        session=auth.session,
        user_id=auth.user_id,
        course_id=course_id,
        document_type=document_type,
        title=title,
        file_content=file_content,
        filename=file.filename,
        background_tasks=background_tasks,
    )


@router.get("/courses/{course_id}/documents", response_model=DocumentList)
async def list_documents(
    course_id: uuid.UUID,
    auth: CurrentAuth,
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DocumentList:
    """List documents for a course."""
    documents, total = await rag_service.list_documents_with_count(
        auth.session,
        auth.user_id,
        course_id,
        skip=skip,
        limit=limit,
    )
    return DocumentList(documents=documents, total=total, page=skip // limit + 1, size=limit)


@router.post("/courses/{course_id}/search", response_model=SearchResponse)
async def search_documents(
    course_id: uuid.UUID,
    search_request: SearchRequest,
    auth: CurrentAuth,
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
) -> SearchResponse:
    """Search documents within a course using RAG."""
    results = await rag_service.search_documents(
        auth.session,
        auth.user_id,
        course_id,
        search_request.query,
        search_request.top_k,
    )
    return SearchResponse(results=results, total=len(results))


@router.delete("/documents/{document_id}", response_model=DefaultResponse)
async def delete_document(
    document_id: int,
    auth: CurrentAuth,
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
) -> DefaultResponse:
    """Delete a document by id, enforcing ownership."""
    await rag_service.delete_document(auth.session, auth.user_id, document_id)
    return DefaultResponse(status=True, message="Document deleted successfully")


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    auth: CurrentAuth,
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
) -> DocumentResponse:
    """Get document details by id, enforcing ownership."""
    return await rag_service.get_document(auth.session, auth.user_id, document_id)
