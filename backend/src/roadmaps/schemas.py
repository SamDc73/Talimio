from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, Field


class RoadmapBase(BaseModel):
    """Base schema for roadmap data."""

    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    skill_level: str = Field(..., pattern="^(beginner|intermediate|advanced)$")


class RoadmapCreate(RoadmapBase):
    """Schema for creating a roadmap."""

    class Config:
        json_schema_extra: ClassVar[dict] = {
            "example": {
                "title": "Machine Learning Engineer Roadmap",
                "description": "Complete roadmap to become an ML engineer",
                "skill_level": "beginner",
            },
        }


class RoadmapUpdate(BaseModel):
    """Schema for updating a roadmap."""

    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, min_length=1)
    skill_level: str | None = Field(None, pattern="^(beginner|intermediate|advanced)$")


class NodeBase(BaseModel):
    """Base schema for node data."""

    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    content: str | None = None
    order: int = Field(default=0, ge=0)
    prerequisite_ids: list[UUID] = Field(default_factory=list)


class NodeCreate(NodeBase):
    """Schema for creating a node."""

    roadmap_id: UUID

    class Config:
        json_schema_extra: ClassVar[dict] = {
            "example": {
                "title": "Python Basics",
                "description": "Learn Python fundamentals",
                "content": "# Python Basics\n\nIn this module...",
                "order": 1,
                "prerequisite_ids": [],
                "roadmap_id": "123e4567-e89b-12d3-a456-426614174000",
            },
        }


class NodeUpdate(BaseModel):
    """Schema for updating a node."""

    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, min_length=1)
    content: str | None = None
    order: int | None = Field(None, ge=0)
    prerequisite_ids: list[UUID] | None = None


class NodeResponse(NodeBase):
    """Schema for node response."""

    id: UUID
    status: str
    roadmap_id: UUID
    created_at: datetime
    updated_at: datetime
    prerequisites: list["NodeResponse"] = []

    class Config:
        from_attributes = True


class RoadmapResponse(RoadmapBase):
    """Schema for roadmap response."""

    id: UUID
    created_at: datetime
    updated_at: datetime
    nodes: list[NodeResponse] = []

    class Config:
        from_attributes = True


class RoadmapsListResponse(BaseModel):
    """Schema for paginated roadmaps response."""

    items: list[RoadmapResponse]
    total: int
    page: int
    pages: int
