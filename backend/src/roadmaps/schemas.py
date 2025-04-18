from datetime import datetime
from typing import Any, ClassVar, ForwardRef
from uuid import UUID

from pydantic import BaseModel as PydanticBaseModel, Field


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
        from_attributes = True

    # Removed custom model_validate. Relying on from_attributes=True.


class RoadmapResponse(RoadmapBase):
    """Schema for roadmap response."""

    id: UUID
    created_at: datetime
    updated_at: datetime
    nodes: list[NodeResponse] = []

    class Config:
        from_attributes = True

    # Removed custom model_validate. Relying on from_attributes=True.


class RoadmapsListResponse(PydanticBaseModel):  # type: ignore[misc]
    """Schema for paginated roadmaps response."""

    items: list[RoadmapResponse]
    total: int
    page: int
    pages: int
