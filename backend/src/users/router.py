from typing import cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.core.exceptions import ResourceNotFoundError, ValidationError
from src.database.session import DbSession
from src.users.schemas import UserCreate, UserResponse, UserUpdate
from src.users.service import UserService


router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)  # type: ignore[misc]
async def create_user(
    data: UserCreate,
    session: DbSession,
) -> UserResponse:
    """Create new user."""
    service = UserService(session)
    try:
        user = await service.create_user(data)
        return cast(UserResponse, UserResponse.model_validate(user))
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get(
    "/{user_id}",
)  # type: ignore[misc]
async def get_user(
    user_id: UUID,
    session: DbSession,
) -> UserResponse:
    """Get user by ID."""
    service = UserService(session)
    try:
        user = await service.get_user(user_id)
        return cast(UserResponse, UserResponse.model_validate(user))
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.put(
    "/{user_id}",
)  # type: ignore[misc]
async def update_user(
    user_id: UUID,
    data: UserUpdate,
    session: DbSession,
) -> UserResponse:
    """Update user."""
    service = UserService(session)
    try:
        user = await service.update_user(user_id, data)
        return cast(UserResponse, UserResponse.model_validate(user))
    except (ResourceNotFoundError, ValidationError) as e:
        status_code = status.HTTP_404_NOT_FOUND if isinstance(e, ResourceNotFoundError) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(e)) from e


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)  # type: ignore[misc]
async def delete_user(
    user_id: UUID,
    session: DbSession,
) -> None:
    """Delete user."""
    service = UserService(session)
    try:
        await service.delete_user(user_id)
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
