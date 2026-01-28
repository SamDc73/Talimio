import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError, IntegrityError, OperationalError
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .ai.assistant.router import router as assistant_router
from .ai.mcp.router import router as mcp_router  # type: ignore[import]
from .ai.rag.router import router as rag_router
from .auth.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenExpiredError,
)
from .auth.middleware import AuthInjectionMiddleware
from .auth.router import router as auth_router
from .books.router import router as books_router

# Setup logging
from .config.logging import setup_logging
from .config.settings import get_settings
from .content.router import router as content_router
from .courses.router import router as courses_router
from .database.migrate import apply_migrations
from .database.session import DbSession, engine
from .exceptions import ResourceNotFoundError, ValidationError as CustomValidationError
from .highlights.router import router as highlights_router
from .middleware.error_handlers import (
    AuthorizationError,
    ErrorCategory,
    ErrorCode,
    ExternalServiceError,
    RateLimitError,
    format_error_response,
    handle_authentication_errors,
    handle_authorization_errors,
    handle_database_errors,
    handle_external_service_errors,
    handle_rate_limit_errors,
    handle_validation_errors,
    log_error_context,
)
from .middleware.security import SimpleSecurityMiddleware, limiter
from .progress.router import router as progress_router
from .tagging.router import router as tagging_router
from .user.router import router as user_router
from .videos.router import router as videos_router


if TYPE_CHECKING:
    from starlette.types import ExceptionHandler


setup_logging()
logger = logging.getLogger(__name__)


def _register_routers(app: FastAPI) -> None:
    """Register all application routers."""
    routers = [
        assistant_router,
        books_router,
        content_router,
        highlights_router,
        progress_router,
        rag_router,
        courses_router,
        tagging_router,
        user_router,
        videos_router,
        auth_router,
        mcp_router,
    ]

    for router in routers:
        app.include_router(router)


async def _startup() -> None:
    """Perform lightweight startup checks and initialization."""
    try:
        from src.ai.rag.config import RAGConfig

        rag_config = RAGConfig()
        if rag_config.embedding_model:
            logger.info("RAG configuration loaded")
    except Exception:
        logger.exception("Failed to load RAG configuration")
        raise

    try:
        from src.auth.validation import validate_auth_on_startup

        validate_auth_on_startup()
    except Exception:
        logger.exception("Auth configuration validation failed")
        raise

    try:
        await apply_migrations(engine)
        logger.info("Database migrations applied")
    except Exception:
        logger.exception("Database migrations failed")
        raise

    try:
        from src.ai.memory import warm_memory_client

        await warm_memory_client()
        logger.info("AsyncMemory client warmed")
    except Exception:
        logger.warning("AsyncMemory client warm-up failed", exc_info=True)


async def _shutdown() -> None:
    """Release resources on shutdown."""
    try:
        from src.ai.memory import cleanup_memory_client

        await cleanup_memory_client()
        logger.info("Memory wrapper cleaned up")
    except Exception:
        logger.warning("Error cleaning up memory wrapper", exc_info=True)

    try:
        await engine.dispose()
        logger.info("Database engine disposed")
    except Exception:
        logger.warning("Error disposing database engine", exc_info=True)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events."""
    await _startup()
    yield
    await _shutdown()


def _configure_middlewares(app: FastAPI, settings: Any) -> None:
    """Register built-in middlewares and rate limiting."""
    app.add_middleware(
        cast("Any", CORSMiddleware),
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(cast("Any", GZipMiddleware), minimum_size=1000)
    app.add_middleware(
        cast("Any", SessionMiddleware),
        secret_key=settings.SECRET_KEY,
        https_only=settings.ENVIRONMENT == "production",
    )
    app.add_middleware(cast("Any", SimpleSecurityMiddleware))
    app.state.limiter = limiter
    # Rate limit handler for RateLimitExceeded is registered in create_app()
    app.add_middleware(cast("Any", AuthInjectionMiddleware))


def _register_exception_handlers(app: FastAPI) -> None:
    """Attach all exception handlers to app."""

    def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> Response:
        return _rate_limit_exceeded_handler(request, exc)

    app.add_exception_handler(RateLimitExceeded, cast("ExceptionHandler", _rate_limit_handler))

    def resource_not_found_handler(_request: Request, exc: ResourceNotFoundError) -> JSONResponse:
        return format_error_response(
            category=ErrorCategory.RESOURCE_NOT_FOUND,
            code=ErrorCode.NOT_FOUND,
            detail=str(exc),
            status_code=404,
            suggestions=["The requested resource does not exist"],
        )

    app.add_exception_handler(ResourceNotFoundError, cast("ExceptionHandler", resource_not_found_handler))

    auth_handler = cast("ExceptionHandler", handle_authentication_errors)
    for exc_type in (
        AuthenticationError,
        InvalidTokenError,
        TokenExpiredError,
        InvalidCredentialsError,
    ):
        app.add_exception_handler(exc_type, auth_handler)

    app.add_exception_handler(AuthorizationError, cast("ExceptionHandler", handle_authorization_errors))

    validation_handler = cast("ExceptionHandler", handle_validation_errors)
    for exc_type in (ValidationError, CustomValidationError):
        app.add_exception_handler(exc_type, validation_handler)

    database_handler = cast("ExceptionHandler", handle_database_errors)
    for exc_type in (IntegrityError, DatabaseError, OperationalError):
        app.add_exception_handler(exc_type, database_handler)

    app.add_exception_handler(ExternalServiceError, cast("ExceptionHandler", handle_external_service_errors))
    app.add_exception_handler(RateLimitError, cast("ExceptionHandler", handle_rate_limit_errors))


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    try:
        settings = get_settings()
    except Exception:
        logger.exception("Failed to load settings")
        raise

    app = FastAPI(
        title="Learning Courses API",
        description="API for managing learning courses",
        version="0.1.0",
        debug=settings.DEBUG,
        lifespan=lifespan if settings.ENVIRONMENT != "test" else None,
    )

    # Middleware and rate limiting
    _configure_middlewares(app, settings)

    # Exception handlers
    _register_exception_handlers(app)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Global exception handler for unhandled errors."""
        from uuid import uuid4

        # Generate error ID for tracking
        error_id = uuid4()

        # Log comprehensive error context
        log_error_context(request, exc, error_id)

        # Return generic error response without exposing internal details
        return format_error_response(
            category=ErrorCategory.INTERNAL,
            code=ErrorCode.INTERNAL,
            detail="An unexpected error occurred",
            status_code=500,
            metadata={"error_id": str(error_id)},
            suggestions=["Please try again later", "If the problem persists, contact support with the error ID"],
        )

    # Register health check endpoint
    @app.get("/health", response_model=None)
    async def health_check(session: DbSession) -> JSONResponse:
        """Check application health status."""
        try:
            await session.execute(text("SELECT 1"))
            return JSONResponse({"status": "healthy", "db": "connected"}, status_code=200)
        except Exception:
            return JSONResponse({"status": "unhealthy", "db": "disconnected"}, status_code=503)

    # Register all routers
    _register_routers(app)

    # Startup tasks are now handled by the lifespan context manager

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    from src.config import env

    host = env("API_HOST", "127.0.0.1")
    port = int(env("API_PORT", "8080"))

    uvicorn.run(app, host=host, port=port)
