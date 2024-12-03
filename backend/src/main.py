import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config.settings import get_settings
from src.database.core import Base
from src.database.session import engine
from src.progress.router import router as progress_router
from src.roadmaps.router import router as roadmaps_router
from src.users.router import router as users_router


# Load .env from project root (parent of backend directory)``
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
        description="API for an AI-powered learning roadmap platform",
        version="1.0.0",
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

    # Register health check endpoint
    @app.get("/health")  # type: ignore[misc]
    async def health_check() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "healthy"}  # Added explicit return

    # Register routers
    app.include_router(roadmaps_router)
    app.include_router(users_router)
    app.include_router(progress_router)

    # Register startup event
    @app.on_event("startup")
    async def startup() -> None:
        """Run startup tasks."""
        try:
            # Just create tables that don't exist yet
            async with engine.begin() as conn:
                # create_all is safe as it only creates missing tables
                await conn.run_sync(Base.metadata.create_all)
        except Exception as e:
            logger.exception(f"Startup failed: {e}")
            raise

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
