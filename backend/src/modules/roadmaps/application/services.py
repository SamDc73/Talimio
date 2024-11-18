import logging
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.schemas import RoadmapCreate, RoadmapUpdate
from ..domain.models import Roadmap


logger = logging.getLogger(__name__)


class RoadmapService:
    """Service for handling roadmap operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_roadmaps(
        self,
        *,
        user_id: UUID | None = None,
        search: str | None = None,
        page: int = 1,
        limit: int = 10,
    ) -> tuple[list[Roadmap], int]:
        """
        Get paginated list of roadmaps.

        Parameters
        ----------
        user_id : Optional[UUID]
            Filter by user ID
        search : Optional[str]
            Search term for title/description
        page : int
            Page number
        limit : int
            Items per page

        Returns
        -------
        Tuple[List[Roadmap], int]
            List of roadmaps and total count
        """
        query = select(Roadmap)

        if search:
            query = query.filter(
                Roadmap.title.ilike(f"%{search}%") |
                Roadmap.description.ilike(f"%{search}%"),
            )

        # Get total count
        total = await self._session.scalar(
            select(func.count()).select_from(query.subquery()),
        ) or 0

        # Apply pagination
        query = query.offset((page - 1) * limit).limit(limit)
        result = await self._session.execute(query)
        roadmaps = result.scalars().all()

        return list(roadmaps), total

    async def get_roadmap(self, roadmap_id: UUID) -> Roadmap | None:
        """Get a single roadmap by ID."""
        query = select(Roadmap).where(Roadmap.id == roadmap_id)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def create_roadmap(self, data: RoadmapCreate) -> Roadmap:
        """Create a new roadmap."""
        logger.info("Creating new roadmap: %s", data.title)
        roadmap = Roadmap(**data.model_dump())
        self._session.add(roadmap)
        await self._session.commit()
        logger.info("Created roadmap with ID: %s", roadmap.id)
        return roadmap

    async def update_roadmap(self, roadmap_id: UUID, data: RoadmapUpdate) -> Roadmap | None:
        """Update an existing roadmap."""
        roadmap = await self.get_roadmap(roadmap_id)
        if not roadmap:
            return None

        for key, value in data.model_dump().items():
            setattr(roadmap, key, value)

        await self._session.commit()
        return roadmap

    async def delete_roadmap(self, roadmap_id: UUID) -> bool:
        """Delete a roadmap."""
        roadmap = await self.get_roadmap(roadmap_id)
        if not roadmap:
            return False

        await self._session.delete(roadmap)
        await self._session.commit()
        return True
