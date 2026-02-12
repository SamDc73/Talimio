"""AuthContext and FastAPI dependencies for centralized auth/ownership.

This introduces a thin AuthContext layer that pairs the authenticated user_id
with an AsyncSession and exposes small ownership helpers. Feature modules should
prefer passing `CurrentAuth` instead of separate user_id/session pairs over time.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Any, TypeVar
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select

import src.auth.crud as local_crud
from src.auth.dependencies import (
    _get_user_id_dependency,
    get_local_session_id_from_state,
    get_local_token_version_from_state,
)
from src.auth.exceptions import InvalidTokenError
from src.config.settings import get_settings
from src.database.session import DbSession


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.user.models import User


T = TypeVar("T")


class AuthContext:
    """Request-scoped user context with ownership helpers.

    Security principle: If a model does not expose a `user_id` column, generic
    ownership helpers will raise, forcing the feature module to implement an
    explicit, safe check (e.g., via joins). This prevents silent under-scoping.
    """

    def __init__(self, user_id: UUID, session: AsyncSession, local_user: User | None = None) -> None:
        self.user_id = user_id
        self.session = session
        self.local_user = local_user

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

        record_attr = getattr(model, id_field)
        user_id_attr = model.user_id
        stmt = select(model).where(record_attr == record_id, user_id_attr == self.user_id)  # ty: ignore[invalid-argument-type]
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{resource_name.capitalize()} not found",
            )
        return row

# FastAPI DI helpers
async def get_auth_context(
    request: Request,
    user_id: Annotated[UUID, Depends(_get_user_id_dependency)],
    session: DbSession,
) -> AuthContext:
    """Build an AuthContext for the current request (preferred)."""
    if get_settings().AUTH_PROVIDER.lower() == "local":
        from src.user.models import User

        user = await session.get(User, user_id)
        if not user or not user.is_active:
            raise InvalidTokenError
        token_version = get_local_token_version_from_state(request)
        if token_version is None or token_version != user.auth_token_version:
            raise InvalidTokenError
        token_session_id = get_local_session_id_from_state(request)
        if token_session_id is not None:
            auth_session = await local_crud.get_auth_session(session, session_id=token_session_id, user_id=user_id)
            if not auth_session:
                raise InvalidTokenError
            if not local_crud.is_auth_session_active(auth_session, now=datetime.now(UTC)):
                raise InvalidTokenError
            await local_crud.touch_auth_session(session, auth_session)
        return AuthContext(user_id=user_id, session=session, local_user=user)

    return AuthContext(user_id=user_id, session=session)


CurrentAuth = Annotated[AuthContext, Depends(get_auth_context)]
