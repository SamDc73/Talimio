from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config.settings import get_settings
from src.modules.roadmaps.api.router import router as roadmaps_router
from src.shared.infrastructure.database import Base, engine


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Learning Roadmap API",
        description="API for an AI-powered learning roadmap platform",
        version="1.0.0",
        debug=settings.DEBUG,
    )

    @app.on_event("startup")
    async def startup() -> None:
        await create_tables()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "healthy"}

    app.include_router(roadmaps_router)

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
