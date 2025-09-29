"""AuthContext (aka UserContext) and FastAPI dependencies for centralized auth/ownership.

This introduces a thin UserContext layer that pairs the authenticated user_id
with an AsyncSession and exposes small ownership helpers. Feature modules should
prefer passing `CurrentAuth` instead of separate user_id/session pairs over time.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, TypeVar
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select

from src.auth.dependencies import _get_user_id
from src.auth.exceptions import NotFoundError
from src.database.session import DbSession


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


T = TypeVar("T")


class UserContext:
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
            raise NotImplementedError(
                msg
            )

        stmt = select(model).where(model.user_id == self.user_id)
        for key, value in filters.items():
            if not hasattr(model, key):
                msg = f"{model.__name__} has no attribute '{key}' for filtering"
                raise AttributeError(msg)
            stmt = stmt.where(getattr(model, key) == value)

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
            raise NotImplementedError(
                msg
            )
        if not hasattr(model, id_field):
            msg = f"{model.__name__} has no id field '{id_field}'"
            raise AttributeError(msg)

        stmt = select(model).where(
            getattr(model, id_field) == record_id, model.user_id == self.user_id
        )
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
        # Map resource types to models (auth module is allowed to know domains)
        model_map = {
            "course": "src.courses.models.Roadmap",
            "book": "src.books.models.Book",
            "video": "src.videos.models.Video",
        }

        if resource_type not in model_map:
            raise NotFoundError(detail=f"Unknown resource type: {resource_type}")

        # Dynamic import to avoid circular dependencies
        module_path, class_name = model_map[resource_type].rsplit(".", 1)
        module = __import__(module_path, fromlist=[class_name])
        model_class = getattr(module, class_name)

        return await self.get_or_404(model_class, resource_id, resource_type)


# FastAPI DI helpers
# New preferred names
AuthContext = UserContext

async def get_auth_context(
    user_id: Annotated[UUID, Depends(_get_user_id)],
    session: DbSession,
) -> AuthContext:
    """Build an AuthContext for the current request (preferred)."""
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
    "/api/v1/assistant/models",
    # Docs/OpenAPI
    "/docs",
    "/redoc",
    "/openapi.json",
]
