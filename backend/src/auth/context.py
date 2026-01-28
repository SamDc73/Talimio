"""AuthContext and FastAPI dependencies for centralized auth/ownership.

This introduces a thin AuthContext layer that pairs the authenticated user_id
with an AsyncSession and exposes small ownership helpers. Feature modules should
prefer passing `CurrentAuth` instead of separate user_id/session pairs over time.
"""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING, Annotated, Any, TypeVar, cast
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select, text

from src.auth.dependencies import _get_user_id
from src.auth.exceptions import NotFoundError
from src.database.session import DbSession


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm.attributes import QueryableAttribute


T = TypeVar("T")
logger = logging.getLogger(__name__)


async def _ensure_local_user(session: AsyncSession, user_id: UUID) -> None:
    """Ensure the current user exists in the local users table when available."""
    try:
        table_check = await session.execute(text("SELECT to_regclass('users')"))
        if table_check.scalar() is None:
            return

        username_hint = str(user_id)
        await session.execute(
            text(
                """
                INSERT INTO users (id, username, password_hash, role)
                VALUES (:uid, :uname, :pwd, 'user')
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"uid": str(user_id), "uname": username_hint, "pwd": "not_used_in_single_user_mode"},
        )
    except Exception:
        with contextlib.suppress(Exception):
            await session.rollback()
        logger.debug("User ensure step failed for %s", user_id, exc_info=True)


class AuthContext:
    """Request-scoped user context with ownership helpers.

    Security principle: If a model does not expose a `user_id` column, generic
    ownership helpers will raise, forcing the feature module to implement an
    explicit, safe check (e.g., via joins). This prevents silent under-scoping.
    """

    def __init__(self, user_id: UUID, session: AsyncSession) -> None:
        self.user_id = user_id
        self.session = session

    async def query_owned(self, model: type[T], /, **filters: Any) -> list[T]:
        """Return all rows for `model` owned by current user, with extra filters.

        Requires `model.user_id` to exist. If missing, raises to prevent unsafe
        queries.
        """
        if not hasattr(model, "user_id"):
            msg = f"Model {model.__name__} has no user_id attribute; implement explicit ownership logic"
            raise NotImplementedError(msg)

        user_id_attr = cast("QueryableAttribute[UUID]", model.user_id)
        stmt = select(model).where(user_id_attr == self.user_id)
        for key, value in filters.items():
            if not hasattr(model, key):
                msg = f"{model.__name__} has no attribute '{key}' for filtering"
                raise AttributeError(msg)
            column_attr = cast("QueryableAttribute[Any]", getattr(model, key))
            stmt = stmt.where(column_attr == value)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_owned(
        self,
        model: type[T],
        record_id: Any,
        *,
        id_field: str = "id",
    ) -> T | None:
        """Fetch a single row by id if owned by the current user.

        Requires `model.user_id` to exist; see class docstring for rationale.
        """
        if not hasattr(model, "user_id"):
            msg = f"Model {model.__name__} has no user_id attribute; implement explicit ownership logic"
            raise NotImplementedError(msg)
        if not hasattr(model, id_field):
            msg = f"{model.__name__} has no id field '{id_field}'"
            raise AttributeError(msg)

        record_attr = cast("QueryableAttribute[Any]", getattr(model, id_field))
        user_id_attr = cast("QueryableAttribute[UUID]", model.user_id)
        stmt = select(model).where(record_attr == record_id, user_id_attr == self.user_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_or_404(
        self,
        model: type[T],
        record_id: Any,
        resource_name: str = "resource",
        *,
        id_field: str = "id",
    ) -> T:
        """Fetch a single row by id or raise 404 if not owned/missing."""
        row = await self.get_owned(model, record_id, id_field=id_field)
        if not row:
            raise NotFoundError(detail=f"{resource_name.capitalize()} not found")
        return row

    async def exists_owned(self, model: type[T], record_id: Any, *, id_field: str = "id") -> bool:
        """Return True if a row exists and is owned by the current user."""
        return (await self.get_owned(model, record_id, id_field=id_field)) is not None

    async def validate_resource(self, resource_type: str, resource_id: Any) -> Any:
        """Validate user has access to a resource by type name.

        This method allows validation without importing domain models directly,
        preventing circular dependencies in infrastructure modules like ai/rag.
        """
        if resource_type == "course":
            from src.courses.models import Course

            model_class = Course
        elif resource_type == "book":
            from src.books.models import Book

            model_class = Book
        elif resource_type == "video":
            from src.videos.models import Video

            model_class = Video
        else:
            raise NotFoundError(detail=f"Unknown resource type: {resource_type}")

        return await self.get_or_404(model_class, resource_id, resource_type)


# FastAPI DI helpers
async def get_auth_context(
    user_id: Annotated[UUID, Depends(_get_user_id)],
    session: DbSession,
) -> AuthContext:
    """Build an AuthContext for the current request (preferred)."""
    await _ensure_local_user(session, user_id)
    return AuthContext(user_id=user_id, session=session)


CurrentAuth = Annotated[AuthContext, Depends(get_auth_context)]


# Centralized list of paths that bypass auth enforcement in the middleware
# Kept here to give ownership of auth concerns to the auth module
AUTH_SKIP_PATHS: list[str] = [
    # Health check
    "/health",
    # Auth routes (these handle their own auth or are public entrypoints)
    "/api/v1/auth/login",
    "/api/v1/auth/signup",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/api/v1/auth/callback",
    "/api/v1/auth/verify",
    "/api/v1/auth/request-password-reset",
    "/api/v1/auth/reset-password",
    # NOTE: /api/v1/auth/me is NOT in skip paths - it needs authentication
    # Public model list for unauthenticated UI model picker
    "/api/v1/assistant/models",
    # Docs/OpenAPI
    "/docs",
    "/redoc",
    "/openapi.json",
]


def is_auth_skip_path(path: str) -> bool:
    """Return True when the request path should bypass auth enforcement."""
    return any(path == skip or path.startswith(f"{skip}/") for skip in AUTH_SKIP_PATHS)
