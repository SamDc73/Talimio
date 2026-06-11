"""Domain exceptions for the RAG module."""

import uuid

from src.exceptions import NotFoundError, UpstreamUnavailableError, ValidationError


class RagCourseNotFoundError(NotFoundError):
    """Raised when a course-scoped RAG operation targets a missing course."""

    def __init__(self, course_id: uuid.UUID) -> None:
        super().__init__("course", str(course_id), feature_area="rag")


class RagValidationError(ValidationError):
    """Raised when RAG request data fails domain validation."""

    def __init__(self, message: str) -> None:
        super().__init__(message, feature_area="rag")


class RagUnavailableError(UpstreamUnavailableError):
    """Raised when RAG infrastructure is temporarily unavailable."""

    def __init__(self, message: str) -> None:
        super().__init__(message, feature_area="rag")
