import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.core.exceptions import ResourceNotFoundError, ValidationError
from src.database.pagination import Paginator
from src.database.session import DbSession
from src.roadmaps.models import Node, Roadmap
from src.roadmaps.schemas import NodeCreate, NodeUpdate, RoadmapCreate, RoadmapUpdate


logger = logging.getLogger(__name__)


class RoadmapService:
    """Service for handling roadmap operations."""

    def __init__(self, session: DbSession) -> None:
        self._session = session

    async def get_roadmaps(
        self,
        *,
        search: str | None = None,
        page: int = 1,
        limit: int = 10,
    ) -> tuple[list[Roadmap], int]:
        """
        Get paginated list of roadmaps.

        Parameters
        ----------
        search : str | None
            Search term for title/description
        page : int
            Page number
        limit : int
            Items per page

        Returns
        -------
        tuple[list[Roadmap], int]
            List of roadmaps and total count
        """
        query = select(Roadmap)

        if search:
            query = query.filter(
                Roadmap.title.ilike(f"%{search}%") | Roadmap.description.ilike(f"%{search}%"),
            )

        paginator = Paginator(page=page, limit=limit)
        return await paginator.paginate(self._session, query)

    async def get_roadmap(self, roadmap_id: UUID) -> Roadmap:
        """
        Get roadmap by ID.

        Parameters
        ----------
        roadmap_id : UUID
            Roadmap ID

        Returns
        -------
        Roadmap
            Roadmap instance

        Raises
        ------
        ResourceNotFoundError
            If roadmap not found
        """
        query = select(Roadmap).where(Roadmap.id == roadmap_id).options(selectinload(Roadmap.nodes))
        result = await self._session.execute(query)
        roadmap = result.scalar_one_or_none()

        if roadmap is None:
            msg = "Roadmap"
            raise ResourceNotFoundError(msg, str(roadmap_id))

        return roadmap

    async def create_roadmap(self, data: RoadmapCreate) -> Roadmap:
        """
        Create a new roadmap.

        Parameters
        ----------
        data : RoadmapCreate
            Roadmap creation data

        Returns
        -------
        Roadmap
            Created roadmap instance
        """
        logger.info("Creating new roadmap: %s", data.title)
        roadmap = Roadmap(**data.model_dump())
        self._session.add(roadmap)
        await self._session.commit()
        logger.info("Created roadmap with ID: %s", roadmap.id)
        return roadmap

    async def update_roadmap(self, roadmap_id: UUID, data: RoadmapUpdate) -> Roadmap:
        """
        Update an existing roadmap.

        Parameters
        ----------
        roadmap_id : UUID
            Roadmap ID
        data : RoadmapUpdate
            Roadmap update data

        Returns
        -------
        Roadmap
            Updated roadmap instance

        Raises
        ------
        ResourceNotFoundError
            If roadmap not found
        """
        roadmap = await self.get_roadmap(roadmap_id)

        # Update fields if provided
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(roadmap, key, value)

        await self._session.commit()
        return roadmap

    async def delete_roadmap(self, roadmap_id: UUID) -> None:
        """
        Delete a roadmap.

        Parameters
        ----------
        roadmap_id : UUID
            Roadmap ID to delete

        Raises
        ------
        ResourceNotFoundError
            If roadmap not found
        """
        roadmap = await self.get_roadmap(roadmap_id)
        if not roadmap:
            msg = "Roadmap"
            raise ResourceNotFoundError(msg, str(roadmap_id))

        await self._session.delete(roadmap)
        await self._session.commit()

    async def create_node(self, roadmap_id: UUID, data: NodeCreate) -> Node:
        """Create a new node.

        Parameters
        ----------
        roadmap_id : UUID
            ID of the roadmap this node belongs to
        data : NodeCreate
            Node creation data

        Returns
        -------
        Node
            Created node instance

        Raises
        ------
        ValidationError
            If prerequisites are invalid
        """
        # Verify roadmap exists
        roadmap = await self.get_roadmap(roadmap_id)
        if not roadmap:
            msg = f"Roadmap {roadmap_id} not found"
            raise ValidationError(msg)

        # Create node instance
        node = Node(
            roadmap_id=roadmap_id,
            title=data.title,
            description=data.description,
            content=data.content,
            order=data.order,
        )
        node.set_status("available")  # Default status

        # Handle prerequisites if any
        if data.prerequisite_ids:
            prerequisites = await self._get_nodes_by_ids(data.prerequisite_ids)
            if len(prerequisites) != len(data.prerequisite_ids):
                msg = "One or more prerequisite nodes not found"
                raise ValidationError(msg)

            if any(p.roadmap_id != roadmap_id for p in prerequisites):
                msg = "All prerequisites must belong to the same roadmap"
                raise ValidationError(msg)

            node.prerequisites.extend(prerequisites)
            node.set_status("locked")  # Node is locked if it has prerequisites

        self._session.add(node)
        await self._session.commit()
        await self._session.refresh(node)
        return node

    async def update_node(
        self,
        roadmap_id: UUID,
        node_id: UUID,
        data: NodeUpdate,
    ) -> Node:
        """
        Update an existing node.

        Parameters
        ----------
        roadmap_id : UUID
            Roadmap ID
        node_id : UUID
            Node ID
        data : NodeUpdate
            Node update data

        Returns
        -------
        Node
            Updated node instance

        Raises
        ------
        ResourceNotFoundError
            If node not found
        ValidationError
            If prerequisites are invalid
        """
        node = await self._get_node(roadmap_id, node_id)
        if not node:
            msg = "Node"
            raise ResourceNotFoundError(msg, str(node_id))

        update_data = data.model_dump(exclude_unset=True)

        # Handle prerequisites separately
        if "prerequisite_ids" in update_data:
            prerequisite_ids = update_data.pop("prerequisite_ids")
            if prerequisite_ids:
                prerequisites = await self._get_nodes_by_ids(prerequisite_ids)
                if len(prerequisites) != len(prerequisite_ids):
                    msg = "One or more prerequisite nodes not found"
                    raise ValidationError(msg)
                node.prerequisites.clear()
                node.prerequisites.extend(prerequisites)
                node.set_status("locked")
            else:
                node.prerequisites.clear()
                node.set_status("available")

        # Update remaining fields
        for key, value in update_data.items():
            setattr(node, key, value)

        await self._session.commit()
        await self._session.refresh(node)
        return node

    async def delete_node(self, roadmap_id: UUID, node_id: UUID) -> None:
        """
        Delete a node from a roadmap.

        Parameters
        ----------
        roadmap_id : UUID
            Roadmap ID
        node_id : UUID
            Node ID

        Raises
        ------
        ResourceNotFoundError
            If node not found
        """
        node = await self._get_node(roadmap_id, node_id)
        if not node:
            msg = "Node"
            raise ResourceNotFoundError(msg, str(node_id))

        await self._session.delete(node)
        await self._session.commit()

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
