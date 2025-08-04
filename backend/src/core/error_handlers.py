"""Centralized error handling system with proper categorization.

This module provides:
1. Comprehensive error categories for different types of failures
2. Consistent error response formatting
3. Proper logging and monitoring integration
4. User-friendly error messages
"""

import logging
from typing import Any
from uuid import UUID

from asyncpg.exceptions import (
    CheckViolationError,
    ForeignKeyViolationError,
    NotNullViolationError,
    UniqueViolationError,
)
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import (
    IntegrityError,
    OperationalError,
)

from src.auth.exceptions import (
    InvalidCredentialsError,
    InvalidTokenError,
    TokenExpiredError,
)


logger = logging.getLogger(__name__)


# === Error Categories ===


class ErrorCategory:
    """Error category constants."""

    AUTHENTICATION = "AUTHENTICATION_ERROR"
    AUTHORIZATION = "AUTHORIZATION_ERROR"
    VALIDATION = "VALIDATION_ERROR"
    DATABASE = "DATABASE_ERROR"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    CONFLICT = "CONFLICT_ERROR"
    EXTERNAL_SERVICE = "EXTERNAL_SERVICE_ERROR"
    RATE_LIMIT = "RATE_LIMIT_ERROR"
    INTERNAL = "INTERNAL_ERROR"


class ErrorCode:
    """Specific error codes for better client handling."""

    # Authentication errors
    AUTH_REQUIRED = "AUTH_REQUIRED"
    INVALID_TOKEN = "INVALID_TOKEN"  # noqa: S105
    TOKEN_EXPIRED = "TOKEN_EXPIRED"  # noqa: S105
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"

    # Authorization errors
    ACCESS_DENIED = "ACCESS_DENIED"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"

    # Validation errors
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_FIELD = "MISSING_FIELD"
    INVALID_FORMAT = "INVALID_FORMAT"

    # Database errors
    DB_CONNECTION_FAILED = "DB_CONNECTION_FAILED"
    DB_CONSTRAINT_VIOLATION = "DB_CONSTRAINT_VIOLATION"
    DB_UNIQUE_VIOLATION = "DB_UNIQUE_VIOLATION"
    DB_FOREIGN_KEY_VIOLATION = "DB_FOREIGN_KEY_VIOLATION"

    # Resource errors
    NOT_FOUND = "NOT_FOUND"
    ALREADY_EXISTS = "ALREADY_EXISTS"

    # External service errors
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"

    # Rate limiting
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # Internal errors
    INTERNAL = "INTERNAL_ERROR"


# === Custom Exception Classes ===


class AuthorizationError(HTTPException):
    """User is authenticated but lacks permissions."""

    def __init__(self, detail: str = "Insufficient permissions") -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class DatabaseConnectionError(HTTPException):
    """Database connection failed."""

    def __init__(self, detail: str = "Database connection failed") -> None:
        super().__init__(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)


class ExternalServiceError(HTTPException):
    """External service (AI, YouTube, etc.) failed."""

    def __init__(self, service: str, detail: str) -> None:
        super().__init__(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"{service} service error: {detail}")


class RateLimitError(HTTPException):
    """Rate limit exceeded."""

    def __init__(self, detail: str = "Rate limit exceeded", retry_after: int | None = None) -> None:
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": str(retry_after)} if retry_after else None,
        )


# === Error Response Formatting ===


def format_error_response(
    category: str,
    code: str,
    detail: str,
    status_code: int,
    suggestions: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> JSONResponse:
    """Format a consistent error response."""
    content = {
        "error": {
            "category": category,
            "code": code,
            "detail": detail,
        }
    }

    if suggestions:
        content["error"]["suggestions"] = suggestions

    if metadata:
        content["error"]["metadata"] = metadata

    return JSONResponse(status_code=status_code, content=content)


# === Exception Handlers ===


async def handle_authentication_errors(request: Request, exc: Exception) -> JSONResponse:
    """Handle authentication-related errors."""
    logger.warning(
        f"Authentication error on {request.method} {request.url.path}: {exc}",
        extra={
            "client_host": request.client.host if request.client else "unknown",
            "error_type": type(exc).__name__,
        },
    )

    if isinstance(exc, InvalidTokenError):
        code = ErrorCode.INVALID_TOKEN
        detail = "The provided token is invalid"
        suggestions = ["Check your authentication token", "Try logging in again"]
    elif isinstance(exc, TokenExpiredError):
        code = ErrorCode.TOKEN_EXPIRED
        detail = "Your session has expired"
        suggestions = ["Please log in again to continue"]
    elif isinstance(exc, InvalidCredentialsError):
        code = ErrorCode.INVALID_CREDENTIALS
        detail = "Invalid email or password"
        suggestions = ["Check your credentials and try again"]
    else:
        code = ErrorCode.AUTH_REQUIRED
        detail = str(exc) or "Authentication required"
        suggestions = ["Please log in to access this resource"]

    return format_error_response(
        category=ErrorCategory.AUTHENTICATION,
        code=code,
        detail=detail,
        status_code=status.HTTP_401_UNAUTHORIZED,
        suggestions=suggestions,
    )


async def handle_authorization_errors(request: Request, exc: AuthorizationError) -> JSONResponse:
    """Handle authorization errors (403)."""
    logger.warning(
        f"Authorization error on {request.method} {request.url.path}: {exc.detail}",
        extra={
            "client_host": request.client.host if request.client else "unknown",
            "user_id": getattr(request.state, "user_id", None),
        },
    )

    return format_error_response(
        category=ErrorCategory.AUTHORIZATION,
        code=ErrorCode.ACCESS_DENIED,
        detail=exc.detail,
        status_code=status.HTTP_403_FORBIDDEN,
        suggestions=["You don't have permission to access this resource"],
    )


async def handle_validation_errors(request: Request, exc: Exception) -> JSONResponse:
    """Handle validation errors from Pydantic and custom validators."""
    logger.info(f"Validation error on {request.method} {request.url.path}", extra={"error": str(exc)})

    if isinstance(exc, PydanticValidationError):
        # Extract field errors from Pydantic
        errors = []
        for error in exc.errors():
            field = " -> ".join(str(loc) for loc in error["loc"])
            errors.append({"field": field, "message": error["msg"], "type": error["type"]})

        return format_error_response(
            category=ErrorCategory.VALIDATION,
            code=ErrorCode.INVALID_INPUT,
            detail="Invalid input data",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            metadata={"errors": errors},
        )
    # Custom validation error
    return format_error_response(
        category=ErrorCategory.VALIDATION,
        code=ErrorCode.INVALID_INPUT,
        detail=str(exc),
        status_code=status.HTTP_400_BAD_REQUEST,
    )


async def handle_database_errors(request: Request, exc: Exception) -> JSONResponse:
    """Handle database-related errors."""
    logger.error(
        f"Database error on {request.method} {request.url.path}: {exc}", extra={"error_type": type(exc).__name__}
    )

    # Map specific database errors to user-friendly messages
    if isinstance(exc, (UniqueViolationError, IntegrityError)) and "unique" in str(exc).lower():
        return format_error_response(
            category=ErrorCategory.DATABASE,
            code=ErrorCode.DB_UNIQUE_VIOLATION,
            detail="This resource already exists",
            status_code=status.HTTP_409_CONFLICT,
            suggestions=["Try using a different identifier"],
        )

    if isinstance(exc, ForeignKeyViolationError):
        return format_error_response(
            category=ErrorCategory.DATABASE,
            code=ErrorCode.DB_FOREIGN_KEY_VIOLATION,
            detail="Referenced resource does not exist",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, (NotNullViolationError, CheckViolationError)):
        return format_error_response(
            category=ErrorCategory.DATABASE,
            code=ErrorCode.DB_CONSTRAINT_VIOLATION,
            detail="Required data is missing or invalid",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, OperationalError):
        return format_error_response(
            category=ErrorCategory.DATABASE,
            code=ErrorCode.DB_CONNECTION_FAILED,
            detail="Database connection error",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            suggestions=["Please try again later"],
        )

    # Generic database error
    return format_error_response(
        category=ErrorCategory.DATABASE,
        code=ErrorCode.INTERNAL,
        detail="A database error occurred",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


async def handle_external_service_errors(request: Request, exc: ExternalServiceError) -> JSONResponse:
    """Handle external service failures."""
    logger.error(f"External service error on {request.method} {request.url.path}: {exc.detail}")

    return format_error_response(
        category=ErrorCategory.EXTERNAL_SERVICE,
        code=ErrorCode.SERVICE_UNAVAILABLE,
        detail=exc.detail,
        status_code=exc.status_code,
        suggestions=["The service is temporarily unavailable", "Please try again later"],
    )


async def handle_rate_limit_errors(request: Request, exc: RateLimitError) -> JSONResponse:
    """Handle rate limiting."""
    logger.warning(
        f"Rate limit exceeded on {request.method} {request.url.path}",
        extra={
            "client_host": request.client.host if request.client else "unknown",
            "user_id": getattr(request.state, "user_id", None),
        },
    )

    return format_error_response(
        category=ErrorCategory.RATE_LIMIT,
        code=ErrorCode.RATE_LIMIT_EXCEEDED,
        detail=exc.detail,
        status_code=exc.status_code,
        suggestions=["Please wait before making more requests"],
        metadata={"retry_after": exc.headers.get("Retry-After")} if exc.headers else None,
    )


# === Utility Functions ===


def log_error_context(request: Request, exc: Exception, error_id: UUID | None = None) -> None:
    """Log comprehensive error context for debugging."""
    context = {
        "error_id": str(error_id) if error_id else None,
        "method": request.method,
        "path": request.url.path,
        "query_params": dict(request.query_params),
        "client_host": request.client.host if request.client else "unknown",
        "user_id": getattr(request.state, "user_id", None),
        "error_type": type(exc).__name__,
        "error_message": str(exc),
    }

    # Add request headers (excluding sensitive ones)
    safe_headers = {
        k: v for k, v in request.headers.items() if k.lower() not in ["authorization", "cookie", "x-api-key"]
    }
    context["headers"] = safe_headers

    logger.error("Request failed", extra=context, exc_info=exc)
