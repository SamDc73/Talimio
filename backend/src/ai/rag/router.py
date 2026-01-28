"""RAG system API router with dependency injection."""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from src.ai.rag.schemas import (
    DefaultResponse,
    DocumentList,
    DocumentResponse,
    SearchRequest,
    SearchResponse,
)
from src.ai.rag.service import RAGService
from src.auth import CurrentAuth


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1", tags=["rag"])


def get_rag_service() -> RAGService:
    """Dependency to get RAG service instance."""
    return RAGService()


# Ownership validation is handled via AuthContext in each endpoint


@router.post("/courses/{course_id}/documents", response_model=DocumentResponse)
async def upload_document(
    course_id: uuid.UUID,
    document_type: Annotated[str, Form()],
    title: Annotated[str, Form()],
    auth: CurrentAuth,
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
    url: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> dict:
    """Upload a document to a course."""
    # Validate course access via AuthContext
    await auth.validate_resource("course", course_id)

    # Only file uploads supported in MVP (no URL crawling)
    if not file:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File upload required")

    if document_type == "url":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL documents not supported in MVP. Please upload a file.",
        )

    file_content = None
    filename = None
    if file:
        file_content = await file.read()
        filename = file.filename

    try:
        result = await rag_service.upload_document(
            auth,
            course_id,
            document_type,
            title,
            file_content,
            url,
            filename,
        )
        return result.model_dump(by_alias=True) if hasattr(result, "model_dump") else result

        # Don't process immediately to avoid blocking
        # TODO: Add to background job queue

    except HTTPException:
        raise
    except ValueError as e:
        # Validation errors
        logger.exception("Validation error uploading document: %s", str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except RuntimeError as e:
        # System errors (API failures, processing errors)
        logger.exception("System error uploading document: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document upload temporarily unavailable",
        ) from e
    except Exception as e:  # pragma: no cover - unexpected safety net
        logger.exception("Unexpected error uploading document")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document",
        ) from e


@router.get("/courses/{course_id}/documents", response_model=DocumentList)
async def list_documents(
    course_id: uuid.UUID,
    auth: CurrentAuth,
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
    skip: int = 0,
    limit: int = 20,
) -> dict:
    """List documents for a course - with graceful failure handling."""
    # Validate course access via AuthContext
    await auth.validate_resource("course", course_id)

    try:
        documents = await rag_service.get_documents(auth, course_id, skip=skip, limit=limit)

        # Get total count
        total = await rag_service.count_documents(auth, course_id)

        result = DocumentList(documents=documents, total=total, page=skip // limit + 1, size=limit)
        return result.model_dump(by_alias=True)

    except Exception:  # pragma: no cover - defensive logging
        # Log but don't crash - return empty list
        logger.exception("Error listing documents for course %s", course_id)
        result = DocumentList(documents=[], total=0, page=1, size=limit)
        return result.model_dump()


@router.post("/courses/{course_id}/search", response_model=SearchResponse)
async def search_documents(
    course_id: uuid.UUID,
    search_request: SearchRequest,
    auth: CurrentAuth,
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
) -> dict:
    """Search documents within a course using RAG."""
    # Validate course access via AuthContext
    await auth.validate_resource("course", course_id)

    try:
        results = await rag_service.search_documents(
            auth,
            course_id,
            search_request.query,
            search_request.top_k,
        )

        result = SearchResponse(results=results, total=len(results))
        return result.model_dump(by_alias=True)

    except ValueError as e:
        # Validation errors
        logger.exception("Validation error searching documents: %s", str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except RuntimeError as e:
        # System errors (API failures, search errors)
        logger.exception("System error searching documents: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document search temporarily unavailable",
        ) from e
    except Exception as e:  # pragma: no cover - unexpected safety net
        logger.exception("Unexpected error searching documents")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search documents",
        ) from e


@router.delete("/documents/{document_id}", response_model=DefaultResponse)
async def delete_document(
    document_id: int,
    auth: CurrentAuth,
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
) -> dict:
    """Delete a document by id, enforcing ownership."""
    try:
        # Validate user owns the document and delete it
        await rag_service.delete_document(auth, document_id)
        result = DefaultResponse(
            status=True,
            message="Document deleted successfully",
        )
        return result.model_dump(by_alias=True)

    except HTTPException:
        # Propagate explicit HTTP errors from the service (e.g., 404)
        raise
    except ValueError as e:
        # Validation errors (e.g., document not found, not owned by user)
        logger.exception("Validation error deleting document: %s", str(e))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except RuntimeError as e:
        # System errors
        logger.exception("System error deleting document: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document deletion temporarily unavailable",
        ) from e
    except Exception as e:  # pragma: no cover - unexpected safety net
        logger.exception("Unexpected error deleting document")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document",
        ) from e


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    auth: CurrentAuth,
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
) -> dict:
    """Get document details by id, enforcing ownership."""
    try:
        result = await rag_service.get_document(auth, document_id)
        return result.model_dump(by_alias=True) if hasattr(result, "model_dump") else result
    except HTTPException:
        # Propagate explicit HTTP errors from the service (e.g., 404)
        raise
    except ValueError as e:
        # Validation errors (kept for backward compatibility if service raises ValueError)
        logger.exception("Validation error getting document: %s", str(e))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except RuntimeError as e:
        # System errors
        logger.exception("System error getting document: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document retrieval temporarily unavailable",
        ) from e
    except Exception as e:  # pragma: no cover - unexpected safety net
        logger.exception("Unexpected error getting document")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get document",
        ) from e


# URL extraction endpoint removed - MVP only supports file uploads
