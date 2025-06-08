import logging
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.ai.client import ModelManager
from src.core.exceptions import ResourceNotFoundError, ValidationError
from src.database.pagination import Paginator
from src.database.session import DbSession
from src.roadmaps.models import Node, Roadmap
from src.roadmaps.schemas import NodeCreate, NodeUpdate, RoadmapCreate, RoadmapResponse, RoadmapUpdate


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
        """Create a new roadmap with foundational nodes.

        Adds detailed logging and clearer error handling for debugging.

        Args:
            data: Roadmap creation data

        Returns
        -------
            Roadmap: Created roadmap instance
        """
        roadmap = Roadmap()
        roadmap.title = data.title
        roadmap.description = data.description
        roadmap.skill_level = data.skill_level
        self._session.add(roadmap)
        await self._session.flush()

        try:
            logger.info(f"Generating initial nodes for roadmap '{data.title}' (level: {data.skill_level})")
            nodes_data = await self.ai_client.generate_roadmap_content(
                title=data.title,
                skill_level=data.skill_level,
                description=data.description,
            )
            logger.info(f"Successfully generated node data: {nodes_data}")
        except Exception as e:
            logger.exception(f"AI client failed to generate roadmap content: {e}")
            await self._session.rollback()
            raise HTTPException(status_code=500, detail=f"AI generation failed: {e}") from e

        try:
            # Recursively create nodes and nested children with proper parent IDs
            logger.info(f"Creating nodes in DB for roadmap '{roadmap.id}'")
            await self._create_nodes_recursive(nodes_data, roadmap.id)
        except Exception as e:
            logger.exception(f"Failed to create nodes in DB: {e}")
            await self._session.rollback()
            raise HTTPException(status_code=500, detail=f"Node creation failed: {e}") from e
        else:
            await self._session.commit()
            logger.info(f"Roadmap '{roadmap.id}' created successfully.")
            return roadmap

    async def _create_nodes_recursive(
        self,
        nodes_data: list[dict],
        roadmap_id: UUID,
        parent_id: UUID | None = None,
    ) -> None:
        """Recursively create nodes and their children, preserving hierarchy."""
        for idx, node_data in enumerate(nodes_data):
            node = Node()
            node.roadmap_id = roadmap_id
            node.title = node_data.get("title", f"Topic {idx + 1}")
            node.description = node_data.get("description", "")
            node.content = node_data.get("content")
            node.order = node_data.get("order", idx)
            node.parent_id = parent_id
            node.status = "not_started"
            self._session.add(node)
            # Flush to generate node.id for children
            await self._session.flush()
            # Recurse into children if any
            children = node_data.get("children") or []
            if children:
                await self._create_nodes_recursive(children, roadmap_id, parent_id=node.id)

    async def update_roadmap(self, roadmap_id: UUID, data: RoadmapUpdate) -> Roadmap:
        """Update an existing roadmap."""
        roadmap = await self.get_roadmap(roadmap_id)

        # Update fields if provided
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(roadmap, key, value)

        await self._session.commit()
        await self._session.refresh(roadmap)
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
                roadmap_id=roadmap_id,
                current_node=data.title,
                progress_level=roadmap.skill_level,
            )

            # Create node with AI-generated content
            node = Node()
            node.roadmap_id = roadmap_id
            node.title = node_content.get("title", "")
            node.description = node_content.get("description", "")
            node.content = node_content.get("content")
            node.order = data.order
            node.status = "not_started"

            self._session.add(node)
        except Exception as e:
            await self._session.rollback()
            logger.exception("Failed to create node with AI content")
            raise ValidationError(str(e)) from e
        else:
            await self._session.commit()
            await self._session.refresh(node)
            return node

    async def update_node(self, roadmap_id: UUID, node_id: UUID, data: NodeUpdate) -> Node:
        """Update an existing node."""
        node = await self._get_node(roadmap_id, node_id)
        if not node:
            msg = "Node"
            raise ResourceNotFoundError(msg, str(node_id))

        update_data = data.model_dump(exclude_unset=True)

        # Remove prerequisite_ids from update data as the feature is removed
        if "prerequisite_ids" in update_data:
            update_data.pop("prerequisite_ids")

        # Update remaining fields
        for key, value in update_data.items():
            setattr(node, key, value)

        await self._session.commit()
        await self._session.refresh(node)
        return node

    async def get_node(self, roadmap_id: UUID, node_id: UUID) -> Node | None:
        """Get a single node from a roadmap."""
        return await self._get_node(roadmap_id, node_id)

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
                roadmap_id=roadmap_id,
                current_node=current_node.title,
                progress_level=roadmap.skill_level,
            )

            # Create new nodes
            new_nodes: list[Node] = []
            # Ensure next_nodes_content is a list of dictionaries
            next_nodes_content_list = (
                [next_nodes_content] if not isinstance(next_nodes_content, list) else next_nodes_content
            )

            for content in next_nodes_content_list:
                if not isinstance(content, dict):
                    continue

                node = Node()
                node.roadmap_id = roadmap_id
                node.title = content.get("title", "")
                node.description = content.get("description", "")
                node.content = content.get("content")
                node.order = current_node.order + 1
                node.status = "not_started"
                self._session.add(node)
                new_nodes.append(node)
        except Exception as e:
            await self._session.rollback()
            logger.exception("Failed to generate next nodes")
            raise ValidationError(str(e)) from e
        else:
            await self._session.commit()
            return new_nodes

    async def generate_sub_nodes(self, roadmap_id: UUID, node_id: UUID) -> list[Node]:
        """Generate sub-nodes for a given node using LLM, providing the full roadmap tree as context."""
        # Fetch the full roadmap with all nodes (nested)
        roadmap = await self.get_roadmap(roadmap_id)
        # Serialize the full roadmap tree
        roadmap_json = RoadmapResponse.model_validate(roadmap).model_dump()

        # Mark the target node in the JSON tree (add a 'target': true flag)
        def mark_target(node_dict: dict) -> None:
            if str(node_dict.get("id")) == str(node_id):
                node_dict["target"] = True
            for child in node_dict.get("children", []):
                mark_target(child)

        for node_dict in roadmap_json.get("nodes", []):
            mark_target(node_dict)

        # Convert prompt to expected format
        prompt_data = [
            {
                "role": "system",
                "content": (
                    "Given the following roadmap structure in JSON, generate 2-3 appropriate sub-nodes for the node marked with 'target': true. "
                    "Each sub-node should have a title and description. Respond with a JSON array of objects with 'title' and 'description'."
                ),
            },
            {
                "role": "user",
                "content": f"Roadmap JSON:\n{roadmap_json}",
            },
        ]

        # Call LLM
        llm_response = await self.ai_client._get_completion(prompt_data)  # noqa: SLF001
        # Parse LLM response (expecting a JSON array)
        import json

        def _raise_type_error() -> None:
            msg = "LLM did not return a list"
            raise TypeError(msg)

        try:
            sub_nodes = json.loads(llm_response) if isinstance(llm_response, str) else llm_response
            if not isinstance(sub_nodes, list):
                _raise_type_error()
        except Exception as e:
            msg = f"Failed to parse LLM response: {e}"
            raise ValidationError(msg) from e

        # Insert new nodes as children of the target node
        parent_node = await self._get_node(roadmap_id, node_id)
        if not parent_node:
            msg = "Node"
            raise ResourceNotFoundError(msg, str(node_id))
        new_nodes = []
        for i, data in enumerate(sub_nodes):
            node = Node()
            node.roadmap_id = roadmap_id
            node.title = data.get("title", "")
            node.description = data.get("description", "")
            node.content = None
            node.order = len(parent_node.children) + i
            node.status = "not_started"
            node.parent_id = parent_node.id
            self._session.add(node)
            new_nodes.append(node)
        await self._session.commit()
        return new_nodes

    async def get_roadmap_json(self, roadmap_id: UUID) -> dict:
        """Get a roadmap serialized to JSON format.

        Args:
            roadmap_id: UUID of the roadmap to serialize

        Returns
        -------
            dict: JSON serialized roadmap with full node tree
        """
        roadmap = await self.get_roadmap(roadmap_id)
        # Serialize the full roadmap tree
        return RoadmapResponse.model_validate(roadmap).model_dump()

    # New methods for direct node access (Phase 2.1)
    async def get_node_direct(self, node_id: UUID) -> Node:
        """Get a node directly by ID without requiring roadmap ID."""
        query = select(Node).where(Node.id == node_id)
        result = await self._session.execute(query)
        node = result.scalar_one_or_none()

        if node is None:
            msg = "Node"
            raise ResourceNotFoundError(msg, str(node_id))

        return node

    async def update_node_direct(self, node_id: UUID, data: NodeUpdate) -> Node:
        """Update a node directly by ID without requiring roadmap ID."""
        node = await self.get_node_direct(node_id)

        update_data = data.model_dump(exclude_unset=True)

        # Remove prerequisite_ids from update data as the feature is removed
        if "prerequisite_ids" in update_data:
            update_data.pop("prerequisite_ids")

        # Update remaining fields
        for key, value in update_data.items():
            setattr(node, key, value)

        await self._session.commit()
        await self._session.refresh(node)
        return node

    async def update_node_status(self, node_id: UUID, status: str) -> Node:
        """Update node status directly by ID."""
        node = await self.get_node_direct(node_id)

        # Validate status
        valid_statuses = ["not_started", "in_progress", "done"]
        if status not in valid_statuses:
            msg = f"Invalid status '{status}'. Valid statuses are: {', '.join(valid_statuses)}"
            raise ValidationError(msg)

        node.status = status

        # Update completion percentage based on status
        if status == "not_started":
            node.completion_percentage = 0.0
        elif status == "in_progress":
            # Keep current percentage if already set, otherwise default to 50%
            if node.completion_percentage == 0.0:
                node.completion_percentage = 50.0
        elif status == "done":
            node.completion_percentage = 100.0

        await self._session.commit()
        await self._session.refresh(node)
        return node

    async def get_roadmap_nodes(self, roadmap_id: UUID) -> list[Node]:
        """Get all nodes for a roadmap with their current status."""
        # Verify roadmap exists
        await self.get_roadmap(roadmap_id)

        # Use selectinload to eagerly load children relationships
        from sqlalchemy.orm import selectinload

        query = (
            select(Node).options(selectinload(Node.children)).where(Node.roadmap_id == roadmap_id).order_by(Node.order)
        )
        result = await self._session.execute(query)
        return list(result.scalars().all())
