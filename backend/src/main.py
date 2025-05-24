import asyncio
import logging
from pathlib import Path

from asyncpg.exceptions import ConnectionDoesNotExistError
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.assistant.router import router as assistant_router
from src.books.models import Book, BookProgress  # Import models to register with SQLAlchemy
from src.books.router import router as books_router
from src.config.settings import get_settings
from src.core.exceptions import ResourceNotFoundError
from src.database.core import Base
from src.database.session import engine
from src.flashcards.models import FlashcardCard, FlashcardDeck, FlashcardReview  # Import models to register with SQLAlchemy
from src.flashcards.router import router as flashcards_router
from src.lessons import router as lessons_router
from src.onboarding.router import router as onboarding_router
from src.progress.router import router as progress_router
from src.roadmaps.router import router as roadmaps_router
from src.videos.models import Video  # Import models to register with SQLAlchemy
from src.videos.router import router as videos_router


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
    app.include_router(flashcards_router)
    app.include_router(roadmaps_router)
    app.include_router(onboarding_router)
    app.include_router(lessons_router)
    app.include_router(progress_router)
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
