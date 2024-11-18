import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from src.shared.infrastructure.database import Base


# Node prerequisites relationship table
node_prerequisites = Table(
    "node_prerequisites",
    Base.metadata,
    Column("node_id", UUID(as_uuid=True), ForeignKey("nodes.id"), primary_key=True),
    Column("prerequisite_id", UUID(as_uuid=True), ForeignKey("nodes.id"), primary_key=True),
)


class Node(Base):
    """Node model."""

    __tablename__ = "nodes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    content = Column(String)
    roadmap_id = Column(
        UUID(as_uuid=True),
        ForeignKey("roadmaps.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    roadmap = relationship("Roadmap", back_populates="nodes")
    prerequisites = relationship(
        "Node",
        secondary=node_prerequisites,
        primaryjoin=id == node_prerequisites.c.node_id,
        secondaryjoin=id == node_prerequisites.c.prerequisite_id,
        lazy="selectin",
    )


class Roadmap(Base):
    """Roadmap model."""

    __tablename__ = "roadmaps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    description = Column(String)
    skill_level = Column(
        Enum("beginner", "intermediate", "advanced", name="skill_level_enum"),
        nullable=False,
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Define relationship after Node class
    nodes = relationship("Node", back_populates="roadmap", lazy="selectin")