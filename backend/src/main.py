import asyncio
import logging
from pathlib import Path

from asyncpg.exceptions import ConnectionDoesNotExistError
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config.settings import get_settings
from src.core.exceptions import ResourceNotFoundError
from src.database.core import Base
from src.database.session import engine
from src.onboarding.router import router as onboarding_router
from src.progress.router import router as progress_router
from src.roadmaps.router import router as roadmaps_router
from src.users.router import router as users_router


# Load .env from project root (parent of backend directory)
ROOT_DIR = Path(__file__).parent.parent.parent
ENV_PATH = ROOT_DIR / ".env"
load_dotenv(ENV_PATH)


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_tables() -> None:
    """Create database tables."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        logger.exception(f"Failed to create tables: {e}")
        raise


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    try:
        settings = get_settings()
    except Exception as e:
        logger.exception(f"Failed to load settings: {e}")
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
        request: Request, exc: ResourceNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc)},
        )

    # Register health check endpoint
    @app.get("/health")  # type: ignore[misc]
    async def health_check() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "healthy"}  # Added explicit return

    # Register routers
    app.include_router(roadmaps_router)
    app.include_router(users_router)
    app.include_router(progress_router)
    app.include_router(onboarding_router)

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

            except ConnectionDoesNotExistError as e:
                if attempt == max_retries - 1:  # Last attempt
                    logger.exception(f"Startup failed after {max_retries} attempts: {e}")
                    raise

                logger.warning(f"Database connection attempt {attempt + 1} failed, retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff

            except Exception as e:
                logger.exception(f"Startup failed with unexpected error: {e}")
                raise

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8080)
