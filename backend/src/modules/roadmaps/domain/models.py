import uuid
from datetime import datetime
from typing import ClassVar, Literal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Table
from sqlalchemy.dialects.postgresql import UUID as SA_UUID
from sqlalchemy.orm import relationship
from src.shared.infrastructure.database import Base


node_prerequisites = Table(
    "node_prerequisites",
    Base.metadata,
    Column("node_id", SA_UUID(as_uuid=True), ForeignKey("nodes.id"), primary_key=True),
    Column(
        "prerequisite_id",
        SA_UUID(as_uuid=True),
        ForeignKey("nodes.id"),
        primary_key=True,
    ),
)


class Roadmap(Base):
    """Roadmap model."""

    __tablename__ = "roadmaps"

    id = Column(SA_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    description = Column(String)
    skill_level: Literal["beginner", "intermediate", "advanced"] = Column(
        Enum("beginner", "intermediate", "advanced", name="skill_level_enum"),
        nullable=False,
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Define relationship after Node class is defined
    nodes = relationship("Node", back_populates="roadmap", lazy="selectin")


class Node(Base):
    """Node model."""

    __tablename__ = "nodes"

    id = Column(SA_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    content = Column(String, nullable=True)
    order = Column(Integer, nullable=False)
    roadmap_id = Column(SA_UUID(as_uuid=True), ForeignKey("roadmaps.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    roadmap = relationship("Roadmap", back_populates="nodes")
    prerequisites = relationship(
        "Node",
        secondary=node_prerequisites,
        primaryjoin=id == node_prerequisites.c.node_id,
        secondaryjoin=id == node_prerequisites.c.prerequisite_id,
        backref="dependents",
    )


class NodeBase(BaseModel):
    """Base schema for a node."""

    id: UUID
    title: str
    description: str
    content: str | None = None
    order: int = Field(..., ge=0)
    roadmap_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NodeUpdate(BaseModel):
    """Schema for updating a node."""

    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, min_length=1)
    content: str | None = None
    order: int | None = Field(None, ge=0)
    prerequisite_ids: list[UUID] | None = None


class NodeResponse(NodeBase):
    """Schema for node response."""

    status: str
    prerequisites: list["NodeResponse"] = []

    class Config:
        from_attributes = True


class RoadmapBase(BaseModel):
    """Base schema for a roadmap."""

    id: UUID
    title: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RoadmapCreate(BaseModel):
    """Schema for creating a roadmap."""

    title: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)


class RoadmapUpdate(BaseModel):
    """Schema for updating a roadmap."""

    title: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)


class RoadmapResponse(RoadmapBase):
    """Schema for roadmap response."""

    nodes: list[NodeResponse] = []

    class Config:
        from_attributes = True


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


# To handle forward references
NodeResponse.update_forward_refs()
