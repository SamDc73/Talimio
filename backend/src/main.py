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

from asyncpg.exceptions import ConnectionDoesNotExistError
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from .ai.rag.router import router as rag_router
from .assistant.router import router as assistant_router
from .auth.manager import auth_manager
from .auth.router import router as auth_router

# Import models to register them with SQLAlchemy - MUST be after database.base import
from .books.models import Book, BookProgress  # noqa: F401
from .books.router import router as books_router
from .config.settings import get_settings
from .content.router import router as content_router
from .core.exceptions import ResourceNotFoundError
from .courses.models import (  # noqa: F401
    Lesson,
    LessonProgress as Progress,
    Node,
    Roadmap,
    RoadmapDocument,
)
from .database.base import Base
from .database.session import engine
from .flashcards.models import FlashcardCard, FlashcardDeck, FlashcardReview  # noqa: F401
from .flashcards.router import router as flashcards_router
from .middleware.auth_error_handler import AuthErrorMiddleware
from .tagging.models import Tag, TagAssociation  # noqa: F401
from .tagging.router import router as tagging_router
from .user.current_user_router import router as current_user_router

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
    def filter(self, record: logging.LogRecord) -> bool:
        # Filter out specific Cohere embedding capability detection warnings
        message = str(record.getMessage())
        return not (
            "Could not detect capabilities for cohere/embed" in message
            or "output_dimension is not supported" in message
        )


# Apply the filter to the root logger to catch all instances
logging.getLogger().addFilter(CohereEmbeddingWarningFilter())


async def create_tables() -> None:
    """Create database tables."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception:
        logger.exception("Failed to create tables")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events."""
    # Startup
    # Validate RAG configuration
    try:
        from src.ai.constants import rag_config

        rag_config.validate_config()
        logger.info("RAG configuration validated successfully")
    except ValueError as e:
        logger.error(f"Invalid RAG configuration: {e}")
        raise

    # Run automatic migrations
    try:
        from src.database.auto_migrate import run_auto_migrations

        await run_auto_migrations()
        logger.info("Database migrations completed")
    except Exception as e:
        logger.error(f"Failed to run migrations: {e}")
        # Continue startup even if migrations fail

    max_retries = 5
    retry_delay = 1  # seconds

    for attempt in range(max_retries):
        try:
            # Initialize database with required extensions FIRST
            from src.database.migrations.init_database import init_database

            await init_database(engine)

            # Create all tables
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            # Run migrations to add any missing columns
            from src.database.migrations.missing_columns import run_all_missing_columns_migrations

            await run_all_missing_columns_migrations(engine)

            # Run auth migration
            from src.database.migrations.user_table import add_user_table

            await add_user_table()

            # Run archive migration
            from src.database.migrations.add_archive_columns import run_archive_migrations

            await run_archive_migrations(engine)

            # Run RAG system migration (pgvector is already enabled by init_database)
            from src.database.migrations.add_rag_system import add_rag_system

            await add_rag_system()

            # Run course references migration
            from src.database.migrations.fix_course_refs import fix_course_references

            await fix_course_references()

            # Run timezone migration for datetime columns
            from src.database.migrations.add_timezone_to_datetime_columns import add_timezone_to_datetime_columns

            await add_timezone_to_datetime_columns(engine)

            # Run RAG status columns migration
            from src.database.migrations.add_rag_status_columns import run_rag_status_migrations

            await run_rag_status_migrations(engine)

            # Run transcript URL migration
            from src.database.migrations.add_transcript_url import run_transcript_url_migration

            await run_transcript_url_migration(engine)

            # Run user custom instructions migration
            from src.database.migrations.add_user_custom_instructions import (
                run_migration as run_custom_instructions_migration,
            )

            await run_custom_instructions_migration(engine)

            break  # Success - exit the retry loop

        except ConnectionDoesNotExistError:
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
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add session middleware for cookie handling
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SECRET_KEY,
        https_only=settings.ENVIRONMENT == "production",
    )

    # Add auth error handling middleware
    app.add_middleware(AuthErrorMiddleware)

    # Global auth middleware - Always set user_id, fallback to DEFAULT_USER_ID
    @app.middleware("http")
    async def inject_user_context(request: Request, call_next):
        """Inject user context into every request."""
        # Get user ID, with AuthManager handling fallbacks to the default user
        request.state.user_id = auth_manager.get_effective_user_id(request)

        response = await call_next(request)
        return response

    # Add exception handlers
    @app.exception_handler(ResourceNotFoundError)
    async def resource_not_found_handler(
        _request: Request,
        exc: ResourceNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc)},
        )

    # Register health check endpoint
    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "healthy"}

    # Register routers
    # Note: Auth router removed - using new auth manager system
    app.include_router(assistant_router)
    app.include_router(books_router)
    app.include_router(content_router)
    app.include_router(flashcards_router)
    app.include_router(rag_router)  # RAG system

    # Course management - new unified API
    from src.courses.router import router as courses_router

    app.include_router(courses_router)

    # Legacy roadmaps API has been removed - all functionality moved to courses API

    app.include_router(tagging_router)
    app.include_router(user_router)
    app.include_router(current_user_router)  # Current user endpoints
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
