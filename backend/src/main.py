import logging
import re
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError, IntegrityError, OperationalError, SQLAlchemyError
from starlette.middleware.sessions import SessionMiddleware
from starlette.routing import Match

from .ai.assistant.router import router as assistant_router
from .ai.litellm_config import cleanup_litellm_async_clients
from .ai.mcp.router import router as mcp_router
from .ai.rag.config import rag_config
from .ai.rag.router import router as rag_router
from .auth.csrf import CSRFMiddlewareWithMaxAge, get_csrf_cookie_domain
from .auth.router import router as auth_router
from .auth.security import get_csrf_signing_key, get_session_signing_key
from .books.router import router as books_router

# Setup logging
from .config.logging import setup_logging
from .config.settings import get_settings
from .content.router import router as content_router
from .courses.router import router as courses_router
from .database.migrate import apply_migrations, assert_migrations_current, validate_vector_schema_dimensions
from .database.session import DbSession, engine
from .exceptions import DomainError, ErrorCategory, ErrorCode
from .highlights.router import router as highlights_router
from .middleware.error_handlers import (
    ExternalServiceError,
    format_error_response,
    handle_database_errors,
    handle_domain_errors,
    handle_external_service_errors,
    handle_http_exception,
    handle_validation_errors,
    log_error_context,
)
from .middleware.security import SimpleSecurityMiddleware
from .observability import configure_observability
from .observability.log_context import update_log_context
from .progress.router import router as progress_router
from .tagging.router import router as tagging_router
from .user.router import router as user_router
from .videos.router import router as videos_router


setup_logging(get_settings())
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
    if rag_config.embedding_model:
        logger.debug("startup.rag.config_loaded")

    settings = get_settings()
    if settings.MIGRATIONS_AUTO_APPLY:
        applied_migrations = await apply_migrations(engine)
        logger.info("startup.migrations.applied", extra={"applied_count": applied_migrations})
    else:
        await assert_migrations_current(engine)
        logger.info("startup.migrations.validated")

    await validate_vector_schema_dimensions(engine)
    logger.info("startup.vector_schema.checked")

    from src.ai.memory import warm_memory_client

    memory_warmed = warm_memory_client()
    logger.info("startup.memory.checked", extra={"warmed": memory_warmed})


async def _shutdown() -> None:
    """Release resources on shutdown."""
    try:
        await cleanup_litellm_async_clients()
        logger.debug("shutdown.litellm.cleaned")
    except (RuntimeError, TimeoutError, TypeError, ValueError):
        logger.warning("shutdown.litellm.cleanup_failed", exc_info=True)

    try:
        from src.ai.memory import cleanup_memory_client

        cleanup_memory_client()
        logger.debug("shutdown.memory.cleaned")
    except (RuntimeError, TimeoutError, TypeError, ValueError):
        logger.warning("shutdown.memory.cleanup_failed", exc_info=True)

    try:
        from src.videos.service import cleanup_detached_video_tasks

        await cleanup_detached_video_tasks()
        logger.debug("shutdown.videos.detached_tasks.cleaned")
    except (RuntimeError, TimeoutError, TypeError, ValueError):
        logger.warning("shutdown.videos.detached_tasks.cleanup_failed", exc_info=True)

    try:
        await engine.dispose()
        logger.debug("shutdown.database_engine.disposed")
    except SQLAlchemyError:
        logger.warning("shutdown.database_engine.dispose_failed", exc_info=True)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan events."""
    await _startup()
    yield
    await _shutdown()


def _get_cors_allow_origins(settings: Any) -> list[str]:
    configured = (getattr(settings, "CORS_ALLOW_ORIGINS", "") or "").strip()
    if configured:
        origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
        if origins:
            return origins

    origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
    frontend_url = getattr(settings, "FRONTEND_URL", "")
    if isinstance(frontend_url, str) and frontend_url:
        parsed = urlsplit(frontend_url)
        if parsed.scheme and parsed.netloc:
            frontend_origin = f"{parsed.scheme}://{parsed.netloc}"
            if frontend_origin not in origins:
                origins.append(frontend_origin)
    return origins


def _configure_middlewares(app: FastAPI, settings: Any) -> None:
    """Register built-in middlewares."""
    session_secret = get_session_signing_key()
    csrf_secret = get_csrf_signing_key()
    app.add_middleware(
        cast("Any", CORSMiddleware),
        allow_origins=_get_cors_allow_origins(settings),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(cast("Any", GZipMiddleware), minimum_size=1000)
    app.add_middleware(
        cast("Any", SessionMiddleware),
        secret_key=session_secret,
        https_only=settings.ENVIRONMENT == "production",
    )
    app.add_middleware(
        cast("Any", CSRFMiddlewareWithMaxAge),
        secret=csrf_secret,
        exempt_urls=[
            re.compile(r"^/api/v1/auth/(login|signup|forgot-password|reset-password|verify|resend-verification)$")
        ],
        sensitive_cookies={settings.AUTH_COOKIE_NAME},
        cookie_domain=get_csrf_cookie_domain(settings.FRONTEND_URL),
        cookie_secure=settings.ENVIRONMENT == "production",
    )
    app.add_middleware(cast("Any", SimpleSecurityMiddleware))


def _register_exception_handlers(app: FastAPI) -> None:
    """Attach all exception handlers to app."""
    app.add_exception_handler(DomainError, cast("Any", handle_domain_errors))
    app.add_exception_handler(HTTPException, cast("Any", handle_http_exception))
    validation_handler = cast("Any", handle_validation_errors)
    for exc_type in (RequestValidationError, ValidationError):
        app.add_exception_handler(exc_type, validation_handler)

    database_handler = cast("Any", handle_database_errors)
    for exc_type in (IntegrityError, DatabaseError, OperationalError):
        app.add_exception_handler(exc_type, database_handler)

    app.add_exception_handler(ExternalServiceError, cast("Any", handle_external_service_errors))

    def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
        error_id = uuid.uuid4()
        update_log_context(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code=str(ErrorCode.INTERNAL),
        )
        log_error_context(request, exc, error_id)
        return format_error_response(
            category=str(ErrorCategory.INTERNAL),
            code=str(ErrorCode.INTERNAL),
            detail="An unexpected error occurred",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            metadata={"error_id": str(error_id)},
            suggestions=["Please try again later", "If the problem persists, contact support with the error ID"],
        )

    app.add_exception_handler(Exception, cast("Any", internal_error_handler))


def _register_frontend_routes(app: FastAPI) -> None:
    """Serve built frontend files when a bundled web app is present."""
    frontend_dist_dir = Path(__file__).resolve().parent.parent / "frontend_dist"
    index_file_path = frontend_dist_dir / "index.html"
    if not index_file_path.exists():
        logger.debug("startup.frontend.bundle_missing", extra={"frontend_dist_dir": str(frontend_dist_dir)})
        return

    assets_dir = frontend_dist_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")

    logo_path = frontend_dist_dir / "logo.png"

    @app.api_route(
        "/api/v1/{api_path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        include_in_schema=False,
        response_model=None,
    )
    def unknown_api_route(request: Request, api_path: str) -> JSONResponse:
        del api_path
        allowed_methods: set[str] = set()
        for route in app.router.routes:
            if getattr(route, "endpoint", None) is unknown_api_route:
                continue

            route_match, _ = route.matches(request.scope)
            if route_match is Match.PARTIAL:
                route_methods = getattr(route, "methods", None)
                if route_methods:
                    allowed_methods.update(route_methods)

        if allowed_methods:
            allow_header = ", ".join(sorted(method for method in allowed_methods if method != "HEAD"))
            response = format_error_response(
                category=str(ErrorCategory.BAD_REQUEST),
                code=str(ErrorCode.METHOD_NOT_ALLOWED),
                detail="Method Not Allowed",
                status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            )
            response.headers["Allow"] = allow_header
            return response

        return format_error_response(
            category=str(ErrorCategory.RESOURCE_NOT_FOUND),
            code=str(ErrorCode.NOT_FOUND),
            detail="Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    @app.get("/logo.png", include_in_schema=False, response_model=None)
    async def serve_frontend_logo() -> FileResponse | JSONResponse:
        if not logo_path.exists():
            return JSONResponse({"detail": "Not Found"}, status_code=status.HTTP_404_NOT_FOUND)
        return FileResponse(logo_path)

    @app.get("/{catchall:path}", include_in_schema=False, response_model=None)
    async def serve_frontend_catchall(_request: Request, catchall: str) -> FileResponse | JSONResponse:
        if catchall.startswith("api/"):
            return format_error_response(
                category=str(ErrorCategory.RESOURCE_NOT_FOUND),
                code=str(ErrorCode.NOT_FOUND),
                detail="Not Found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return FileResponse(index_file_path)


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Learning Courses API",
        description="API for managing learning courses",
        version="0.1.0",
        debug=settings.DEBUG,
        lifespan=lifespan if settings.ENVIRONMENT != "test" else None,
    )

    # Middleware
    _configure_middlewares(app, settings)

    # Exception handlers
    _register_exception_handlers(app)

    # Register health check endpoint
    @app.get("/health", response_model=None)
    async def health_check(session: DbSession) -> JSONResponse:
        """Check application health status."""
        try:
            await session.execute(text("SELECT 1"))
            return JSONResponse({"status": "healthy", "db": "connected"}, status_code=status.HTTP_200_OK)
        except (DatabaseError, OperationalError):
            return JSONResponse(
                {"status": "unhealthy", "db": "disconnected"}, status_code=status.HTTP_503_SERVICE_UNAVAILABLE
            )

    # Register all routers
    _register_routers(app)

    # Register frontend routes if a bundled SPA is present.
    _register_frontend_routes(app)

    configure_observability(app, settings=settings, engine=engine)

    # Startup tasks are now handled by the lifespan context manager

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    from src.config import env

    host = env("API_HOST", "127.0.0.1")
    port = int(env("API_PORT", "8080"))

    uvicorn.run(app, host=host, port=port)
