import logging
from uuid import UUID

from sqlalchemy import select

from src.core.exceptions import ResourceNotFoundError, ValidationError
from src.database.pagination import Paginator
from src.database.session import DbSession
from src.progress.models import Progress
from src.progress.schemas import ProgressCreate, ProgressUpdate
from src.roadmaps.models import Node
from src.users.models import User


logger = logging.getLogger(__name__)


class ProgressService:
    """Service for handling progress operations."""

    def __init__(self, session: DbSession) -> None:
        self._session = session

    async def create_progress(self, data: ProgressCreate) -> Progress:
        """
        Create a new progress record.

        Parameters
        ----------
        data : ProgressCreate
            Progress creation data

        Returns
        -------
        Progress
            Created progress instance

        Raises
        ------
        ValidationError
            If user or node doesn't exist
        """
        # Verify user exists
        user = await self._get_user(data.user_id)
        if not user:
            msg = f"User {data.user_id} not found"
            raise ValidationError(msg)

        # Verify node exists
        node = await self._get_node(data.node_id)
        if not node:
            msg = f"Node {data.node_id} not found"
            raise ValidationError(msg)

        # Check if progress already exists
        existing = await self._get_progress_by_user_and_node(data.user_id, data.node_id)
        if existing:
            msg = "Progress record already exists for this user and node"
            raise ValidationError(msg)

        progress = Progress(**data.model_dump())
        self._session.add(progress)
        await self._session.commit()
        return progress

    async def get_progress(self, progress_id: UUID) -> Progress:
        """
        Get progress by ID.

        Parameters
        ----------
        progress_id : UUID
            Progress ID

        Returns
        -------
        Progress
            Progress instance

        Raises
        ------
        ResourceNotFoundError
            If progress not found
        """
        query = select(Progress).where(Progress.id == progress_id)
        result = await self._session.execute(query)
        progress = result.scalar_one_or_none()

        if not progress:
            msg = "Progress"
            raise ResourceNotFoundError(msg, str(progress_id))

        return progress

    async def get_user_progress(
        self,
        user_id: UUID,
        *,
        page: int = 1,
        limit: int = 10,
    ) -> tuple[list[Progress], int]:
        """
        Get all progress records for a user.

        Parameters
        ----------
        user_id : UUID
            User ID
        page : int
            Page number
        limit : int
            Items per page

        Returns
        -------
        tuple[list[Progress], int]
            List of progress records and total count

        Raises
        ------
        ValidationError
            If user doesn't exist
        """
        # Verify user exists
        user = await self._get_user(user_id)
        if not user:
            msg = f"User {user_id} not found"
            raise ValidationError(msg)

        query = select(Progress).where(Progress.user_id == user_id)
        paginator = Paginator(page=page, limit=limit)
        return await paginator.paginate(self._session, query)

    async def update_progress(
        self,
        progress_id: UUID,
        data: ProgressUpdate,
    ) -> Progress:
        """
        Update progress.

        Parameters
        ----------
        progress_id : UUID
            Progress ID
        data : ProgressUpdate
            Progress update data

        Returns
        -------
        Progress
            Updated progress instance

        Raises
        ------
        ResourceNotFoundError
            If progress not found
        ValidationError
            If status is invalid
        """
        progress = await self.get_progress(progress_id)

        # Validate status transition
        progress = await self.get_progress(progress_id)

        # Get the current status as string
        current_status = str(progress.status) if progress.status else "not_started"

        # Validate status transition
        if data.status and not self._is_valid_status_transition(current_status, data.status):
            msg = f"Invalid status transition from {current_status} to {data.status}"
            raise ValidationError(msg)

        # Update fields
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(progress, key, value)

        await self._session.commit()
        return progress

    async def delete_progress(self, progress_id: UUID) -> None:
        """
        Delete progress record.

        Parameters
        ----------
        progress_id : UUID
            Progress ID to delete

        Raises
        ------
        ResourceNotFoundError
            If progress record not found
        """
        progress = await self.get_progress(progress_id)

        await self._session.delete(progress)
        await self._session.commit()

    async def _get_user(self, user_id: UUID) -> User | None:
        """Get user by ID."""
        query = select(User).where(User.id == user_id)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def _get_node(self, node_id: UUID) -> Node | None:
        """Get node by ID."""
        query = select(Node).where(Node.id == node_id)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def _get_progress_by_user_and_node(
        self,
        user_id: UUID,
        node_id: UUID,
    ) -> Progress | None:
        """Get progress record by user and node IDs."""
        query = select(Progress).where(
            Progress.user_id == user_id,
            Progress.node_id == node_id,
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    def _is_valid_status_transition(self, current: str, new: str) -> bool:
        """
        Validate status transition.

        Valid transitions:
        - not_started -> in_progress
        - in_progress -> completed
        - completed -> in_progress (for revision)

        Parameters
        ----------
        current : str
            Current status
        new : str
            New status

        Returns
        -------
        bool
            Whether the transition is valid
        """
        valid_transitions = {
            "not_started": ["in_progress"],
            "in_progress": ["completed"],
            "completed": ["in_progress"],  # Allow going back for revision
        }

        return new in valid_transitions.get(current, [])
