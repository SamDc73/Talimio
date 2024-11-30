import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.core.exceptions import ResourceNotFoundError, ValidationError
from src.database.session import DbSession
from src.users.models import User
from src.users.schemas import UserCreate, UserUpdate


logger = logging.getLogger(__name__)


class UserService:
    """Service for handling user operations."""

    def __init__(self, session: DbSession) -> None:
        self._session = session

    async def create_user(self, data: UserCreate) -> User:
        """
        Create a new user.

        Parameters
        ----------
        data : UserCreate
            User creation data

        Returns
        -------
        User
            Created user instance

        Raises
        ------
        ValidationError
            If email already exists
        """
        logger.info("Creating new user with email: %s", data.email)
        user = User(**data.model_dump())
        self._session.add(user)

        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            msg = f"User with email {data.email} already exists"
            raise ValidationError(msg)

        logger.info("Created user with ID: %s", user.id)
        return user

    async def get_user(self, user_id: UUID) -> User:
        """
        Get user by ID.

        Parameters
        ----------
        user_id : UUID
            User ID

        Returns
        -------
        User
            User instance

        Raises
        ------
        ResourceNotFoundError
            If user not found
        """
        query = select(User).where(User.id == user_id)
        result = await self._session.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            msg = "User"
            raise ResourceNotFoundError(msg, str(user_id))

        return user

    async def get_user_by_email(self, email: str) -> User | None:
        """
        Get user by email.

        Parameters
        ----------
        email : str
            User email

        Returns
        -------
        User | None
            User instance if found, None otherwise
        """
        query = select(User).where(User.email == email)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def update_user(self, user_id: UUID, data: UserUpdate) -> User:
        """
        Update user.

        Parameters
        ----------
        user_id : UUID
            User ID
        data : UserUpdate
            User update data

        Returns
        -------
        User
            Updated user instance

        Raises
        ------
        ResourceNotFoundError
            If user not found
        ValidationError
            If email already exists
        """
        # First get the user to ensure it exists
        user = await self.get_user(user_id)

        # Update fields
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(user, key, value)

        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            msg = f"User with email {data.email} already exists"
            raise ValidationError(msg)

        return user

    async def delete_user(self, user_id: UUID) -> None:
        """
        Delete user.

        Parameters
        ----------
        user_id : UUID
            User ID

        Raises
        ------
        ResourceNotFoundError
            If user not found
        """
        user = await self.get_user(user_id)
        await self._session.delete(user)
        await self._session.commit()
