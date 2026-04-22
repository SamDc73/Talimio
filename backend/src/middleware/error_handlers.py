"""Centralized error handling system with consistent error envelopes."""

import logging
import uuid
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from psycopg.errors import (
    CheckViolation as CheckViolationError,
    ForeignKeyViolation as ForeignKeyViolationError,
    NotNullViolation as NotNullViolationError,
    UniqueViolation as UniqueViolationError,
)
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import IntegrityError, OperationalError

from src.exceptions import ApiError, ApiErrorEnvelope, DomainError, ErrorCategory, ErrorCode
from src.observability.log_context import update_log_context


logger = logging.getLogger(__name__)
POSTGRES_UNIQUE_VIOLATION_SQLSTATE = "23505"
DATABASE_HANDLED_EVENT_NAME = "error.database.handled"


class ExternalServiceError(HTTPException):
    """Transport-layer external dependency failure used at the API boundary."""

    def __init__(self, service: str, detail: str) -> None:
        message = f"{service} service error: {detail}"
        super().__init__(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=message)


def _get_route_path(request: Request) -> str:
    """Return the matched route path template when available."""
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if isinstance(route_path, str):
        return route_path
    return request.url.path


def format_error_response(
    category: str,
    code: str,
    detail: str,
    status_code: int,
    suggestions: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> JSONResponse:
    """Format a consistent error response."""
    payload = ApiErrorEnvelope(
        error=ApiError(
            category=category,
            code=code,
            detail=detail,
            suggestions=suggestions,
            metadata=metadata,
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json", by_alias=True, exclude_none=True),
    )


def handle_http_exception(_request: Request, exc: HTTPException) -> JSONResponse:
    """Map transport-layer HTTP exceptions to the canonical error envelope."""
    category, code = _resolve_http_exception_contract(exc.status_code)
    detail, metadata = _normalize_http_exception_detail(exc.detail)
    update_log_context(status_code=exc.status_code, error_code=code)
    return format_error_response(
        category=str(category),
        code=str(code),
        detail=detail,
        status_code=exc.status_code,
        metadata=metadata,
    )


def handle_domain_errors(request: Request, exc: DomainError) -> JSONResponse:
    """Handle domain exceptions via the shared taxonomy."""
    route = _get_route_path(request)
    update_log_context(status_code=exc.status_code, error_code=exc.error_code)
    logger.warning(
        "error.domain.handled",
        extra={
            "event_name": "error.domain.handled",
            "method": request.method,
            "error_code": exc.error_code,
            "feature_area": exc.feature_area,
            "route": route,
        },
    )
    return format_error_response(
        category=str(exc.category),
        code=exc.error_code,
        detail=str(exc),
        status_code=exc.status_code,
        suggestions=exc.suggestions,
        metadata=exc.metadata,
    )


def handle_validation_errors(request: Request, exc: PydanticValidationError) -> JSONResponse:
    """Handle request-shape validation errors from Pydantic/FastAPI."""
    errors: list[dict[str, str]] = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        errors.append({"field": field, "message": error["msg"], "type": error["type"]})

    route = _get_route_path(request)
    error_code = str(ErrorCode.INVALID_INPUT)
    update_log_context(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, error_code=error_code)
    logger.warning(
        "error.validation.handled",
        extra={
            "event_name": "error.validation.handled",
            "method": request.method,
            "error_code": error_code,
            "route": route,
            "validation_errors": errors,
        },
    )

    return format_error_response(
        category=str(ErrorCategory.VALIDATION),
        code=error_code,
        detail="Invalid input data",
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        metadata={"errors": errors},
    )


def handle_database_errors(request: Request, exc: Exception) -> JSONResponse:
    """Handle database-related errors."""
    route = _get_route_path(request)
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = str(ErrorCode.INTERNAL)
    detail = "A database error occurred"
    suggestions: list[str] | None = None
    severity = "error"

    if _is_unique_violation_error(exc):
        status_code = status.HTTP_409_CONFLICT
        error_code = str(ErrorCode.DB_UNIQUE_VIOLATION)
        detail = "This resource already exists"
        suggestions = ["Try using a different identifier"]
        severity = "warning"
    elif isinstance(exc, ForeignKeyViolationError):
        status_code = status.HTTP_400_BAD_REQUEST
        error_code = str(ErrorCode.DB_FOREIGN_KEY_VIOLATION)
        detail = "Referenced resource does not exist"
        severity = "warning"
    elif isinstance(exc, (NotNullViolationError, CheckViolationError)):
        status_code = status.HTTP_400_BAD_REQUEST
        error_code = str(ErrorCode.DB_CONSTRAINT_VIOLATION)
        detail = "Required data is missing or invalid"
        severity = "warning"
    elif isinstance(exc, OperationalError):
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        error_code = str(ErrorCode.DB_CONNECTION_FAILED)
        detail = "Database connection error"
        suggestions = ["Please try again later"]

    update_log_context(status_code=status_code, error_code=error_code)
    log_extra = {
        "event_name": DATABASE_HANDLED_EVENT_NAME,
        "method": request.method,
        "route": route,
        "error_code": error_code,
        "error_type": type(exc).__name__,
        "status_code": status_code,
    }
    log_level = logging.WARNING if severity == "warning" else logging.ERROR
    log_kwargs: dict[str, Any] = {"extra": log_extra}
    if log_level == logging.ERROR:
        log_kwargs["exc_info"] = (type(exc), exc, exc.__traceback__)
    logger.log(log_level, "error.database.handled", **log_kwargs)

    return format_error_response(
        category=str(ErrorCategory.DATABASE),
        code=error_code,
        detail=detail,
        status_code=status_code,
        suggestions=suggestions,
    )


def _is_unique_violation_error(exc: Exception) -> bool:
    """Return True when exception resolves to SQLSTATE 23505."""
    if isinstance(exc, UniqueViolationError):
        return True

    if not isinstance(exc, IntegrityError):
        return False

    original_error = getattr(exc, "orig", None)
    if original_error is None:
        return False

    sqlstate = getattr(original_error, "sqlstate", None)
    if isinstance(sqlstate, str):
        return sqlstate == POSTGRES_UNIQUE_VIOLATION_SQLSTATE

    pgcode = getattr(original_error, "pgcode", None)
    if isinstance(pgcode, str):
        return pgcode == POSTGRES_UNIQUE_VIOLATION_SQLSTATE

    return False


def handle_external_service_errors(request: Request, exc: ExternalServiceError) -> JSONResponse:
    """Handle external service failures."""
    route = _get_route_path(request)
    error_code = str(ErrorCode.SERVICE_UNAVAILABLE)
    update_log_context(status_code=exc.status_code, error_code=error_code)
    logger.error(
        "error.external_service.handled",
        extra={
            "event_name": "error.external_service.handled",
            "method": request.method,
            "error_code": error_code,
            "route": route,
            "status_code": exc.status_code,
        },
    )

    return format_error_response(
        category=str(ErrorCategory.EXTERNAL_SERVICE),
        code=error_code,
        detail=exc.detail,
        status_code=exc.status_code,
        suggestions=["The service is temporarily unavailable", "Please try again later"],
    )


def log_error_context(request: Request, exc: Exception, error_id: uuid.UUID | None = None) -> None:
    """Log a minimal request context for unexpected exceptions."""
    route = _get_route_path(request)
    context = {
        "event_name": "error.unexpected.request_failed",
        "error_code": str(ErrorCode.INTERNAL),
        "error_id": str(error_id) if error_id else None,
        "method": request.method,
        "route": route,
        "path": request.url.path,
        "query_param_keys": sorted(request.query_params.keys()),
        "header_names": sorted(request.headers.keys()),
        "client_host": request.client.host if request.client else "unknown",
        "user_id": getattr(request.state, "user_id", None),
        "error_type": type(exc).__name__,
    }

    logger.error("error.unexpected.request_failed", extra=context, exc_info=(type(exc), exc, exc.__traceback__))


def _normalize_http_exception_detail(detail: Any) -> tuple[str, dict[str, Any] | None]:
    """Normalize HTTPException detail payloads to the canonical envelope."""
    if isinstance(detail, str):
        return detail, None

    if detail is None:
        return "Request failed", None

    return "Request failed", {"detail": detail}


def _resolve_http_exception_contract(status_code: int) -> tuple[ErrorCategory, ErrorCode]:
    """Map HTTP status codes to canonical error categories and codes."""
    exact_mappings: dict[int, tuple[ErrorCategory, ErrorCode]] = {
        status.HTTP_401_UNAUTHORIZED: (ErrorCategory.AUTHENTICATION, ErrorCode.UNAUTHORIZED),
        status.HTTP_403_FORBIDDEN: (ErrorCategory.FORBIDDEN, ErrorCode.FORBIDDEN),
        status.HTTP_404_NOT_FOUND: (ErrorCategory.RESOURCE_NOT_FOUND, ErrorCode.NOT_FOUND),
        status.HTTP_405_METHOD_NOT_ALLOWED: (ErrorCategory.BAD_REQUEST, ErrorCode.METHOD_NOT_ALLOWED),
        status.HTTP_409_CONFLICT: (ErrorCategory.CONFLICT, ErrorCode.CONFLICT),
        status.HTTP_422_UNPROCESSABLE_CONTENT: (ErrorCategory.VALIDATION, ErrorCode.INVALID_INPUT),
        status.HTTP_501_NOT_IMPLEMENTED: (ErrorCategory.INTERNAL, ErrorCode.NOT_IMPLEMENTED),
    }
    if status_code in exact_mappings:
        return exact_mappings[status_code]

    if status_code in {
        status.HTTP_502_BAD_GATEWAY,
        status.HTTP_503_SERVICE_UNAVAILABLE,
        status.HTTP_504_GATEWAY_TIMEOUT,
    }:
        return ErrorCategory.UPSTREAM_UNAVAILABLE, ErrorCode.UPSTREAM_UNAVAILABLE
    if 400 <= status_code < 500:
        return ErrorCategory.BAD_REQUEST, ErrorCode.BAD_REQUEST
    return ErrorCategory.INTERNAL, ErrorCode.INTERNAL
