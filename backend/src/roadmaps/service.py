import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.ai.client import ModelManager
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
        self.ai_client = ModelManager()

    async def get_roadmaps(
        self,
        *,
        search: str | None = None,
        page: int = 1,
        limit: int = 10,
    ) -> tuple[list[Roadmap], int]:
        """Get paginated list of roadmaps."""
        query = select(Roadmap)

        if search:
            query = query.filter(
                Roadmap.title.ilike(f"%{search}%") | Roadmap.description.ilike(f"%{search}%"),
            )

        paginator = Paginator(page=page, limit=limit)
        return await paginator.paginate(self._session, query)

    async def get_roadmap(self, roadmap_id: UUID) -> Roadmap:
        """Get roadmap by ID."""
        query = select(Roadmap).where(Roadmap.id == roadmap_id).options(selectinload(Roadmap.nodes))
        result = await self._session.execute(query)
        roadmap = result.scalar_one_or_none()

        if roadmap is None:
            msg = "Roadmap"
            raise ResourceNotFoundError(msg, str(roadmap_id))

        return roadmap

    async def create_roadmap(self, data: RoadmapCreate) -> Roadmap:
        """Create a new roadmap with foundational nodes."""
        roadmap = Roadmap(title=data.title, description=data.description, skill_level=data.skill_level)
        self._session.add(roadmap)
        await self._session.flush()

        try:
            # Generate initial nodes
            nodes_data = await self.ai_client.generate_roadmap_content(
                title=data.title, skill_level=data.skill_level, description=data.description
            )

            # Create nodes sequentially
            for node_data in nodes_data:
                node = Node(
                    roadmap_id=roadmap.id,
                    title=node_data["title"],
                    description=node_data["description"],
                    content=node_data["content"],
                    order=node_data["order"],
                    status="not_started",
                )
                self._session.add(node)

            await self._session.commit()
            return roadmap

        except Exception as e:
            await self._session.rollback()
            raise HTTPException(status_code=500, detail=str(e))

    async def update_roadmap(self, roadmap_id: UUID, data: RoadmapUpdate) -> Roadmap:
        """Update an existing roadmap."""
        roadmap = await self.get_roadmap(roadmap_id)

        # Update fields if provided
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(roadmap, key, value)

        await self._session.commit()
        return roadmap

    async def delete_roadmap(self, roadmap_id: UUID) -> None:
        """Delete a roadmap."""
        roadmap = await self.get_roadmap(roadmap_id)
        await self._session.delete(roadmap)
        await self._session.commit()

    async def create_node(self, roadmap_id: UUID, data: NodeCreate) -> Node:
        """Create a new node using AI-generated content."""
        # Verify roadmap exists
        roadmap = await self.get_roadmap(roadmap_id)

        try:
            # Generate node content using AI
            node_content = await self.ai_client.generate_node_content(
                roadmap_id=roadmap_id, current_node=data.title, progress_level=roadmap.skill_level
            )

            # Create node with AI-generated content
            node = Node(
                roadmap_id=roadmap_id,
                title=node_content["title"],
                description=node_content["description"],
                content=node_content["content"],
                order=data.order,
                status="not_started",
            )

            # Handle prerequisites if any
            if node_content.get("prerequisites"):
                prerequisites = await self._get_nodes_by_titles(roadmap_id, node_content["prerequisites"])
                node.prerequisites.extend(prerequisites)

            self._session.add(node)
            await self._session.commit()
            await self._session.refresh(node)
            return node

        except Exception as e:
            await self._session.rollback()
            logger.exception("Failed to create node with AI content")
            raise ValidationError(str(e)) from e

    async def update_node(self, roadmap_id: UUID, node_id: UUID, data: NodeUpdate) -> Node:
        """Update an existing node."""
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
            else:
                node.prerequisites.clear()

        # Update remaining fields
        for key, value in update_data.items():
            setattr(node, key, value)

        await self._session.commit()
        await self._session.refresh(node)
        return node

    async def delete_node(self, roadmap_id: UUID, node_id: UUID) -> None:
        """Delete a node from a roadmap."""
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

    async def _get_nodes_by_titles(self, roadmap_id: UUID, titles: list[str]) -> list[Node]:
        """Get nodes by their titles within a roadmap."""
        query = select(Node).where(Node.roadmap_id == roadmap_id, Node.title.in_(titles))
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def generate_next_nodes(self, roadmap_id: UUID, current_node_id: UUID) -> list[Node]:
        """Generate next nodes based on current progress."""
        current_node = await self._get_node(roadmap_id, current_node_id)
        if not current_node:
            msg = "Node"
            raise ResourceNotFoundError(msg, str(current_node_id))

        roadmap = await self.get_roadmap(roadmap_id)

        try:
            # Generate content for new nodes
            next_nodes_content = await self.ai_client.generate_node_content(
                roadmap_id=roadmap_id, current_node=current_node.title, progress_level=roadmap.skill_level
            )

            # Create new nodes
            new_nodes = []
            for content in next_nodes_content:
                node = Node(
                    roadmap_id=roadmap_id,
                    title=content["title"],
                    description=content["description"],
                    content=content["content"],
                    order=current_node.order + 1,
                    status="not_started",
                )
                node.prerequisites.append(current_node)
                self._session.add(node)
                new_nodes.append(node)

            await self._session.commit()
            return new_nodes

        except Exception as e:
            await self._session.rollback()
            logger.exception("Failed to generate next nodes")
            raise ValidationError(str(e)) from e
