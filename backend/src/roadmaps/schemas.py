from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar
from uuid import UUID

from pydantic import BaseModel as PydanticBaseModel, Field


if TYPE_CHECKING:
    from .models import Node


# Removed ForwardRef definition here


class RoadmapBase(PydanticBaseModel):  # type: ignore[misc]
    """Base schema for roadmap data."""

    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    skill_level: str = Field(..., pattern="^(beginner|intermediate|advanced)$")


class RoadmapCreate(RoadmapBase):
    """Schema for creating a roadmap."""

    title: str
    description: str
    skill_level: str = Field(..., pattern="^(beginner|intermediate|advanced)$")

    class Config:
        """Configuration for the RoadmapCreate schema."""

        json_schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "title": "Machine Learning Engineer Roadmap",
                "description": "Complete roadmap to become an ML engineer",
                "skill_level": "beginner",
            },
        }


class RoadmapUpdate(PydanticBaseModel):  # type: ignore[misc]
    """Schema for updating a roadmap."""

    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, min_length=1)
    skill_level: str | None = Field(None, pattern="^(beginner|intermediate|advanced)$")


class NodeBase(PydanticBaseModel):  # type: ignore[misc]
    """Base schema for node data."""

    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    content: str | None = None
    order: int = Field(default=0, ge=0)
    prerequisite_ids: list[UUID] = Field(default_factory=list)
    parent_id: UUID | None = Field(None, description="Parent node ID if this is a sub-node.")


class NodeCreate(NodeBase):
    """Schema for creating a node."""

    roadmap_id: UUID

    class Config:
        """Configuration for Pydantic model with JSON schema example."""

        json_schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "title": "Python Basics",
                "description": "Learn Python fundamentals",
                "content": "# Python Basics\n\nIn this module...",
                "order": 1,
                "prerequisite_ids": [],
                "roadmap_id": "123e4567-e89b-12d3-a456-426614174000",
                "parent_id": None,
            },
        }


class NodeUpdate(PydanticBaseModel):  # type: ignore[misc]
    """Schema for updating a node."""

    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, min_length=1)
    content: str | None = None
    order: int | None = Field(None, ge=0)
    prerequisite_ids: list[UUID] | None = None
    parent_id: UUID | None = Field(None, description="Parent node ID if this is a sub-node.")


class NodeResponse(NodeBase):
    """Schema for node response."""

    id: UUID
    status: str
    roadmap_id: UUID
    created_at: datetime
    updated_at: datetime
    prerequisite_ids: list[UUID] = Field(default_factory=list)
    # Use string literal for recursive type hint
    children: list["NodeResponse"] = Field(default_factory=list, description="Child nodes (sub-nodes)")

    class Config:
        """Configuration for Pydantic model to support ORM model conversion."""

        from_attributes = True

    # Removed custom model_validate. Relying on from_attributes=True.


class RoadmapResponse(RoadmapBase):
    """Schema for roadmap response."""

    id: UUID
    created_at: datetime
    updated_at: datetime
    nodes: list[NodeResponse] = []  # Will be overridden in model_validate

    class Config:
        """Configuration for Pydantic model to support ORM model conversion."""

        from_attributes = True

    @classmethod
    def model_validate(
        cls,
        obj: object,
        *,
        _strict: bool | None = False,
        _from_attributes: bool | None = False,
        _context: dict | None = None,
        _by_alias: bool | None = False,
        _by_name: bool | None = False,
    ) -> "RoadmapResponse":
        """Validate and convert database model to Pydantic model with nested structure.

        Args:
            obj: Database model object to validate
            strict: If True, strict validation is performed
            from_attributes: Whether to extract data from object attributes
            context: Additional context for validation
            by_alias: Whether to use alias names
            by_name: Whether to match fields by name instead of alias

        Returns
        -------
            RoadmapResponse: Validated response model with properly nested nodes
        """
        # Patch: Build pure nested nodes for 'nodes' field
        roadmap = super().model_validate(obj)
        # Only use root nodes in top-level nodes
        all_nodes = getattr(obj, "nodes", [])
        nested = [NodeResponse.model_validate(node) for node in all_nodes if getattr(node, "parent_id", None) is None]
        roadmap.nodes = nested
        return roadmap


def build_nested_nodes(all_nodes: list["Node"], parent_id: object = None) -> list[dict[str, Any]]:
    """
    Recursively build a pure nested node structure for serialization.

    Each node appears only once, as either a root or a child.
    """
    nested = []
    for node in all_nodes:
        if getattr(node, "parent_id", None) == parent_id:
            node_dict = NodeResponse.model_validate(node).model_dump()
            # Recursively add children
            node_dict["children"] = build_nested_nodes(all_nodes, parent_id=node.id)
            nested.append(node_dict)
    return nested


class RoadmapsListResponse(PydanticBaseModel):
    """Schema for paginated roadmaps response."""

    items: list[RoadmapResponse]
    total: int
    page: int
    pages: int
