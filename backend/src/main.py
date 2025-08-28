import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv


# Load .env FIRST before any other imports that might need env vars
BACKEND_DIR = Path(__file__).parent.parent
ENV_PATH = BACKEND_DIR / ".env"
load_dotenv(ENV_PATH)

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import DatabaseError, IntegrityError, OperationalError
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request

from .ai.rag.router import router as rag_router
from .assistant.router import router as assistant_router
from .auth.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenExpiredError,
)
from .auth.router import router as auth_router

# Import models to register them with SQLAlchemy - MUST be after database.base import
from .books.models import Book, BookProgress  # noqa: F401
from .books.router import router as books_router
from .config.settings import get_settings
from .content.router import router as content_router
from .core.error_handlers import (
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
from .core.exceptions import ResourceNotFoundError, ValidationError as CustomValidationError
from .courses.models import (  # noqa: F401
    Lesson,
    LessonProgress as Progress,
    Node,
    Roadmap,
    RoadmapDocument,
)
from .database.session import engine
from .flashcards.models import FlashcardCard, FlashcardDeck, FlashcardReview  # noqa: F401
from .flashcards.router import router as flashcards_router
from .highlights.models import Highlight  # noqa: F401
from .highlights.router import router as highlights_router
from .middleware.auth_error_handler import AuthErrorMiddleware
from .middleware.security import SimpleSecurityMiddleware, limiter
from .progress.router import router as progress_router
from .tagging.models import Tag, TagAssociation  # noqa: F401
from .tagging.router import router as tagging_router

# Auth models moved to user.models - import for SQLAlchemy registration
from .user.models import User, UserPreferences  # noqa: F401
from .user.router import router as user_router
from .videos.models import Video  # noqa: F401
from .videos.router import router as videos_router


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress LiteLLM capability detection warnings for Cohere embeddings
# These warnings occur during startup when LiteLLM tests if models support certain parameters
litellm_logger = logging.getLogger("LiteLLM")
litellm_logger.setLevel(logging.ERROR)  # Only show errors, not warnings


# Alternatively, create a custom filter for specific Cohere embedding errors
class CohereEmbeddingWarningFilter(logging.Filter):
    """Filter out Cohere embedding capability detection warnings."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter out specific Cohere embedding warnings."""
        # Filter out specific Cohere embedding capability detection warnings
        message = str(record.getMessage())
        return not (
            "Could not detect capabilities for cohere/embed" in message
            or "output_dimension is not supported" in message
        )


# Apply the filter to the root logger to catch all instances
logging.getLogger().addFilter(CohereEmbeddingWarningFilter())


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events."""
    # Startup
    # Validate RAG configuration
    try:
        from src.ai.constants import rag_config

        rag_config.validate_config()
        logger.info("RAG configuration validated successfully")
    except ValueError as e:
        logger.exception(f"Invalid RAG configuration: {e}")
        raise

    # Validate authentication configuration
    try:
        from src.core.auth_config_validator import validate_auth_on_startup

        validate_auth_on_startup()
    except Exception as e:
        logger.exception(f"Auth configuration validation failed: {e}")
        raise

    # Initialize database with simple setup
    max_retries = 5
    retry_delay = 1  # seconds

    for attempt in range(max_retries):
        try:
            # Initialize database with extensions and create all tables
            from src.database.init import init_database

            await init_database(engine)
            logger.info("Database initialization completed successfully")

            break  # Success - exit the retry loop

        except OperationalError:
            if attempt == max_retries - 1:  # Last attempt
                logger.exception("Startup failed after %d attempts", max_retries)
                raise

            logger.warning(
                "Database connection attempt %d failed, retrying in %ds...",
                attempt + 1,
                retry_delay,
            )
            await asyncio.sleep(retry_delay)
            retry_delay *= 2  # Exponential backoff

        except Exception:
            logger.exception("Startup failed with unexpected error")
            raise

    yield
    # Shutdown (if needed)


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    try:
        settings = get_settings()
    except Exception:
        logger.exception("Failed to load settings")
        raise

    app = FastAPI(
        title="Learning Roadmap API",
        description="API for managing learning roadmaps",
        version="0.1.0",
        debug=settings.DEBUG,
        lifespan=lifespan if settings.ENVIRONMENT != "test" else None,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add gzip compression middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Add session middleware for cookie handling
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SECRET_KEY,
        https_only=settings.ENVIRONMENT == "production",
    )

    # Add security middleware (headers + basic protection)
    app.add_middleware(SimpleSecurityMiddleware)

    # Add auth error handling middleware
    app.add_middleware(AuthErrorMiddleware)

    # Add rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Global auth middleware - Always set user_id, fallback to DEFAULT_USER_ID
    @app.middleware("http")
    async def inject_user_context(request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Inject user context into every request."""
        # Skip authentication for certain endpoints
        path = request.url.path
        auth_skip_paths = [
            "/health",
            "/health/db",
            "/health/auth",
            "/api/v1/auth/login",
            "/api/v1/auth/signup",
            "/api/v1/auth/refresh",
            "/api/v1/auth/logout",
            "/api/v1/auth/callback",
            "/api/v1/auth/verify",
            "/api/v1/auth/request-password-reset",
            "/api/v1/auth/reset-password",
            "/api/v1/auth/me",  # This endpoint handles its own auth
            "/api/v1/auth/debug",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]

        # Also skip any static files
        if any(path.startswith(skip_path) for skip_path in auth_skip_paths) or path.startswith("/static"):
            # For auth endpoints, don't try to get user_id
            request.state.user_id = None
        else:
            # Get user ID for protected endpoints
            try:
                from src.auth.config import get_user_id

                request.state.user_id = await get_user_id(request)
            except Exception as e:
                # Import auth exceptions
                from src.auth.exceptions import (
                    AuthenticationError,
                    InvalidTokenError,
                    MissingTokenError,
                    TokenExpiredError,
                )
                from src.core.error_handlers import handle_authentication_errors

                # Log the error for debugging
                logger.error(f"Auth error in middleware for {path}: {type(e).__name__}: {e}")

                # Handle auth errors directly in middleware since exception handlers don't catch middleware errors
                if isinstance(e, (AuthenticationError, InvalidTokenError, MissingTokenError, TokenExpiredError)):
                    return await handle_authentication_errors(request, e)

                # For other errors, let them propagate
                raise

        return await call_next(request)

    # Add exception handlers
    @app.exception_handler(ResourceNotFoundError)
    async def resource_not_found_handler(
        _request: Request,
        exc: ResourceNotFoundError,
    ) -> JSONResponse:
        return format_error_response(
            category=ErrorCategory.RESOURCE_NOT_FOUND,
            code=ErrorCode.NOT_FOUND,
            detail=str(exc),
            status_code=404,
            suggestions=["The requested resource does not exist"],
        )

    # Authentication errors (401)
    @app.exception_handler(AuthenticationError)
    async def auth_error_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
        return await handle_authentication_errors(request, exc)

    @app.exception_handler(InvalidTokenError)
    async def invalid_token_handler(request: Request, exc: InvalidTokenError) -> JSONResponse:
        return await handle_authentication_errors(request, exc)

    @app.exception_handler(TokenExpiredError)
    async def token_expired_handler(request: Request, exc: TokenExpiredError) -> JSONResponse:
        return await handle_authentication_errors(request, exc)

    @app.exception_handler(InvalidCredentialsError)
    async def invalid_credentials_handler(request: Request, exc: InvalidCredentialsError) -> JSONResponse:
        return await handle_authentication_errors(request, exc)

    # Authorization errors (403)
    @app.exception_handler(AuthorizationError)
    async def authorization_error_handler(request: Request, exc: AuthorizationError) -> JSONResponse:
        return await handle_authorization_errors(request, exc)

    # Validation errors (400/422)
    @app.exception_handler(ValidationError)
    async def pydantic_validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
        return await handle_validation_errors(request, exc)

    @app.exception_handler(CustomValidationError)
    async def custom_validation_handler(request: Request, exc: CustomValidationError) -> JSONResponse:
        return await handle_validation_errors(request, exc)

    # Database errors
    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        return await handle_database_errors(request, exc)

    @app.exception_handler(DatabaseError)
    async def database_error_handler(request: Request, exc: DatabaseError) -> JSONResponse:
        return await handle_database_errors(request, exc)

    @app.exception_handler(OperationalError)
    async def operational_error_handler(request: Request, exc: OperationalError) -> JSONResponse:
        return await handle_database_errors(request, exc)

    # External service errors (503)
    @app.exception_handler(ExternalServiceError)
    async def external_service_handler(request: Request, exc: ExternalServiceError) -> JSONResponse:
        return await handle_external_service_errors(request, exc)

    # Rate limit errors (429)
    @app.exception_handler(RateLimitError)
    async def rate_limit_handler(request: Request, exc: RateLimitError) -> JSONResponse:
        return await handle_rate_limit_errors(request, exc)

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

    # Register health check endpoints
    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Check application health status."""
        return {"status": "healthy"}

    @app.get("/health/db")
    async def health_check_db() -> dict[str, str]:
        """Database health check endpoint."""
        try:
            from sqlalchemy import text

            from src.database.session import async_session_maker

            async with async_session_maker() as session:
                # Simple query to check database connectivity
                await session.execute(text("SELECT 1"))
            return {"db_status": "healthy"}
        except Exception as e:
            logger.exception("Database health check failed")
            return JSONResponse(status_code=503, content={"db_status": "unhealthy", "error": str(e)})

    @app.get("/health/auth")
    async def health_check_auth() -> dict[str, str]:
        """Auth service health check endpoint."""
        try:
            settings = get_settings()
            if settings.AUTH_PROVIDER == "supabase":
                # Test Supabase connectivity (basic check)
                # This is a simple check - could be expanded to test actual Supabase connection
                return {"auth_status": "healthy", "provider": "supabase"}
            return {"auth_status": "healthy", "provider": "none"}
        except Exception as e:
            logger.exception("Auth health check failed")
            return JSONResponse(status_code=503, content={"auth_status": "unhealthy", "error": str(e)})

    # Register routers
    # Note: Auth router removed - using new auth manager system
    app.include_router(assistant_router)
    app.include_router(books_router)
    app.include_router(content_router)
    app.include_router(flashcards_router)
    app.include_router(highlights_router)  # Highlights for books, videos, courses
    app.include_router(progress_router)  # Unified progress tracking
    app.include_router(rag_router)  # RAG system

    # Course management - new unified API
    from src.courses.router import router as courses_router

    app.include_router(courses_router)

    # Legacy roadmaps API has been removed - all functionality moved to courses API

    app.include_router(tagging_router)
    app.include_router(user_router)
    app.include_router(videos_router)
    app.include_router(auth_router)

    # Startup tasks are now handled by the lifespan context manager

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    from src.config import env

    host = env("API_HOST", "127.0.0.1")
    port = int(env("API_PORT", "8080"))

    uvicorn.run(app, host=host, port=port)
