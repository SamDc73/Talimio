from enum import StrEnum
from typing import Any

from fastapi import status
from pydantic import BaseModel

from src.config.schema_casing import build_camel_config


CANONICAL_ERROR_LOG_FIELDS: tuple[str, ...] = (
    "event",
    "error_code",
    "feature_area",
    "route",
    "user_id",
    "course_id",
    "content_type",
    "model_name",
)


class ErrorCategory(StrEnum):
    """Canonical backend error categories."""

    AUTHENTICATION = "AUTHENTICATION_ERROR"
    BAD_REQUEST = "BAD_REQUEST_ERROR"
    VALIDATION = "VALIDATION_ERROR"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    CONFLICT = "CONFLICT_ERROR"
    FORBIDDEN = "FORBIDDEN_ERROR"
    UPSTREAM_UNAVAILABLE = "UPSTREAM_UNAVAILABLE_ERROR"
    DATABASE = "DATABASE_ERROR"
    EXTERNAL_SERVICE = "EXTERNAL_SERVICE_ERROR"
    INTERNAL = "INTERNAL_ERROR"


class ErrorCode(StrEnum):
    """Canonical backend error codes."""

    BAD_REQUEST = "BAD_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    INVALID_INPUT = "INVALID_INPUT"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    FORBIDDEN = "FORBIDDEN"
    UPSTREAM_UNAVAILABLE = "UPSTREAM_UNAVAILABLE"
    DB_CONNECTION_FAILED = "DB_CONNECTION_FAILED"
    DB_CONSTRAINT_VIOLATION = "DB_CONSTRAINT_VIOLATION"
    DB_UNIQUE_VIOLATION = "DB_UNIQUE_VIOLATION"
    DB_FOREIGN_KEY_VIOLATION = "DB_FOREIGN_KEY_VIOLATION"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INTERNAL = "INTERNAL_ERROR"


class ApiError(BaseModel):
    """Canonical API error payload."""

    model_config = build_camel_config()

    category: str
    code: str
    detail: str
    suggestions: list[str] | None = None
    metadata: dict[str, Any] | None = None


class ApiErrorEnvelope(BaseModel):
    """Canonical API error envelope."""

    model_config = build_camel_config()

    error: ApiError


class DomainError(Exception):
    """Base exception class for all domain-specific exceptions."""

    category: ErrorCategory = ErrorCategory.BAD_REQUEST
    status_code: int = status.HTTP_400_BAD_REQUEST
    default_error_code: ErrorCode = ErrorCode.BAD_REQUEST

    def __init__(
        self,
        message: str,
        *,
        error_code: str | ErrorCode | None = None,
        metadata: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        feature_area: str | None = None,
        status_code: int | None = None,
        category: ErrorCategory | None = None,
    ) -> None:
        self.message = message
        self.error_code = str(error_code or self.default_error_code)
        self.metadata = metadata
        self.suggestions = suggestions
        self.feature_area = feature_area
        if status_code is not None:
            self.status_code = status_code
        if category is not None:
            self.category = category
        super().__init__(message)


class BadRequestError(DomainError):
    """Exception raised when a request is invalid for domain reasons."""

    category = ErrorCategory.BAD_REQUEST
    status_code = status.HTTP_400_BAD_REQUEST
    default_error_code = ErrorCode.BAD_REQUEST


class ValidationError(DomainError):
    """Exception raised when domain validation fails."""

    category = ErrorCategory.VALIDATION
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_error_code = ErrorCode.INVALID_INPUT


class ForbiddenError(DomainError):
    """Exception raised when access is forbidden."""

    category = ErrorCategory.FORBIDDEN
    status_code = status.HTTP_403_FORBIDDEN
    default_error_code = ErrorCode.FORBIDDEN


class ConflictError(DomainError):
    """Exception raised when a domain conflict occurs."""

    category = ErrorCategory.CONFLICT
    status_code = status.HTTP_409_CONFLICT
    default_error_code = ErrorCode.CONFLICT


class NotFoundError(DomainError):
    """Exception raised when a requested resource is not found."""

    category = ErrorCategory.RESOURCE_NOT_FOUND
    status_code = status.HTTP_404_NOT_FOUND
    default_error_code = ErrorCode.NOT_FOUND

    def __init__(
        self,
        resource_type: str | None = None,
        resource_id: str | None = None,
        *,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        feature_area: str | None = None,
    ) -> None:
        self.resource_type = resource_type
        self.resource_id = resource_id

        if message is None:
            if resource_type and resource_id:
                message = f"{resource_type} with ID {resource_id} not found"
            elif resource_type:
                message = f"{resource_type} not found"
            else:
                message = "Resource not found"

        super().__init__(
            message,
            metadata=metadata,
            suggestions=suggestions,
            feature_area=feature_area,
        )


class UpstreamUnavailableError(DomainError):
    """Exception raised when an upstream dependency is unavailable."""

    category = ErrorCategory.UPSTREAM_UNAVAILABLE
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_error_code = ErrorCode.UPSTREAM_UNAVAILABLE
