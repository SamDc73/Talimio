"""Domain exceptions for the RAG module."""

import uuid

from fastapi import status

from src.exceptions import BadRequestError, ErrorCode, NotFoundError, UpstreamUnavailableError, ValidationError


class RagCourseNotFoundError(NotFoundError):
    """Raised when a course-scoped RAG operation targets a missing course."""

    def __init__(self, course_id: uuid.UUID) -> None:
        super().__init__("course", str(course_id), feature_area="rag")


class RagDocumentNotFoundError(NotFoundError):
    """Raised when a RAG document cannot be found."""

    def __init__(self, document_id: int) -> None:
        super().__init__("document", str(document_id), feature_area="rag")


class RagValidationError(ValidationError):
    """Raised when RAG request data fails domain validation."""

    def __init__(self, message: str) -> None:
        super().__init__(message, feature_area="rag")


class RagUploadTooLargeError(BadRequestError):
    """Raised when an uploaded RAG file exceeds the configured size limit."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            feature_area="rag",
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            error_code=ErrorCode.PAYLOAD_TOO_LARGE,
        )


class RagUnavailableError(UpstreamUnavailableError):
    """Raised when RAG infrastructure is temporarily unavailable."""

    def __init__(self, message: str) -> None:
        super().__init__(message, feature_area="rag")
