import logging
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions.base import ResourceNotFoundException
from ..api.schemas import NodeCreate, NodeUpdate, RoadmapCreate, RoadmapUpdate
from ..domain.models import Node, Roadmap


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


    async def create_node(self, roadmap_id: UUID, data: NodeCreate) -> Node:
        """Create a new node in a roadmap."""
        # Verify roadmap exists
        roadmap = await self.get_roadmap(roadmap_id)
        if not roadmap:
            msg = "Roadmap"
            raise ResourceNotFoundException(msg, str(roadmap_id))

        # Create node
        node = Node(
            roadmap_id=roadmap_id,
            title=data.title,
            description=data.description,
            content=data.content,
            order=data.order,
        )

        # Add prerequisites if any
        if data.prerequisite_ids:
            prerequisites = await self._get_nodes_by_ids(data.prerequisite_ids)
            node.prerequisites.extend(prerequisites)

        # Set initial status based on prerequisites
        node.status = "available" if not data.prerequisite_ids else "locked"

        self._session.add(node)
        await self._session.commit()
        await self._session.refresh(node)

        return node

    async def update_node(
        self, roadmap_id: UUID, node_id: UUID, data: NodeUpdate,
    ) -> Node | None:
        """Update an existing node."""
        node = await self._get_node(roadmap_id, node_id)
        if not node:
            return None

        # Update fields if provided
        if data.title is not None:
            node.title = data.title
        if data.description is not None:
            node.description = data.description
        if data.content is not None:
            node.content = data.content
        if data.order is not None:
            node.order = data.order
        if data.prerequisite_ids is not None:
            prerequisites = await self._get_nodes_by_ids(data.prerequisite_ids)
            node.prerequisites = prerequisites

        await self._session.commit()
        await self._session.refresh(node)
        return node

    async def delete_node(self, roadmap_id: UUID, node_id: UUID) -> bool:
        """Delete a node from a roadmap."""
        node = await self._get_node(roadmap_id, node_id)
        if not node:
            return False

        await self._session.delete(node)
        await self._session.commit()
        return True

    async def _get_node(self, roadmap_id: UUID, node_id: UUID) -> Node | None:
        """Get a node by ID and verify it belongs to the specified roadmap."""
        query = select(Node).where(
            Node.id == node_id,
            Node.roadmap_id == roadmap_id,
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def _get_nodes_by_ids(self, node_ids: list[UUID]) -> list[Node]:
        """Get multiple nodes by their IDs."""
        query = select(Node).where(Node.id.in_(node_ids))
        result = await self._session.execute(query)
        return list(result.scalars().all())
