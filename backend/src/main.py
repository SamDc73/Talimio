import asyncio
import logging
from pathlib import Path

from asyncpg.exceptions import ConnectionDoesNotExistError
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .assistant.router import router as assistant_router

# Import models to register them with SQLAlchemy - MUST be after database.base import
from .books.models import Book, BookProgress  # noqa: F401
from .books.router import router as books_router
from .config.settings import get_settings
from .content.router import router as content_router
from .core.exceptions import ResourceNotFoundError
from .database.base import Base
from .database.session import engine
from .flashcards.models import FlashcardCard, FlashcardDeck, FlashcardReview  # noqa: F401
from .flashcards.router import router as flashcards_router
from .lessons import router as lessons_router
from .onboarding.router import router as onboarding_router
from .progress.models import Progress  # noqa: F401
from .progress.router import router as progress_router
from .roadmaps.models import Node, Roadmap  # noqa: F401
from .roadmaps.router import router as roadmaps_router
from .tagging.models import Tag, TagAssociation  # noqa: F401
from .tagging.router import router as tagging_router
from .videos.models import Video  # noqa: F401
from .videos.router import router as videos_router


# Load .env from backend directory (parent of src)
BACKEND_DIR = Path(__file__).parent.parent
ENV_PATH = BACKEND_DIR / ".env"
load_dotenv(ENV_PATH)


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_tables() -> None:
    """Create database tables."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception:
        logger.exception("Failed to create tables")
        raise


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
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
    app.include_router(assistant_router)
    app.include_router(books_router)
    app.include_router(content_router)
    app.include_router(flashcards_router)
    app.include_router(roadmaps_router)
    app.include_router(onboarding_router)
    app.include_router(lessons_router)
    app.include_router(progress_router)
    app.include_router(tagging_router)
    app.include_router(videos_router)

    # Register startup event
    @app.on_event("startup")
    async def startup() -> None:
        """Run startup tasks."""
        max_retries = 5
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)

                # Run migrations to add any missing columns
                from src.database.add_missing_columns import run_migrations

                await run_migrations(engine)

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

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8080)
