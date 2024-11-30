from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.core.exceptions import ResourceNotFoundError, ValidationError
from src.database.session import DbSession
from src.users.schemas import UserCreate, UserResponse, UserUpdate
from src.users.service import UserService


router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    session: DbSession,
) -> UserResponse:
    """Create new user."""
    service = UserService(session)
    try:
        user = await service.create_user(data)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    return UserResponse.model_validate(user)


@router.get("/{user_id}")
async def get_user(
    user_id: UUID,
    session: DbSession,
) -> UserResponse:
    """
    Get user by ID.

    Parameters
    ----------
    user_id : UUID
        User ID
    session : DbSession
        Database session

    Returns
    -------
    UserResponse
        User response

    Raises
    ------
    HTTPException
        If user not found
    """
    service = UserService(session)
    try:
        user = await service.get_user(user_id)
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    return UserResponse.model_validate(user)


@router.put("/{user_id}")
async def update_user(
    user_id: UUID,
    data: UserUpdate,
    session: DbSession,
) -> UserResponse:
    """
    Update user.

    Parameters
    ----------
    user_id : UUID
        User ID
    data : UserUpdate
        User update data
    session : DbSession
        Database session

    Returns
    -------
    UserResponse
        Updated user response

    Raises
    ------
    HTTPException
        If user not found or validation fails
    """
    service = UserService(session)
    try:
        user = await service.update_user(user_id, data)
    except (ResourceNotFoundError, ValidationError) as e:
        status_code = status.HTTP_404_NOT_FOUND if isinstance(e, ResourceNotFoundError) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(e)) from e
    return UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    session: DbSession,
) -> None:
    """
    Delete user.

    Parameters
    ----------
    user_id : UUID
        User ID
    session : DbSession
        Database session

    Raises
    ------
    HTTPException
        If user not found
    """
    service = UserService(session)
    try:
        await service.delete_user(user_id)
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
