import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Table
from sqlalchemy.dialects.postgresql import UUID as SA_UUID
from sqlalchemy.orm import relationship

from src.database.core import Base


# Association table for node prerequisites
node_prerequisites = Table(
    "node_prerequisites",
    Base.metadata,
    Column(
        "node_id",
        SA_UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "prerequisite_id",
        SA_UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Roadmap(Base):
    """Roadmap model."""

    __tablename__ = "roadmaps"

    id = Column(SA_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(200), nullable=False)
    description = Column(String, nullable=False)
    skill_level = Column(
        Enum("beginner", "intermediate", "advanced", name="skill_level_enum"),
        nullable=False,
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    nodes = relationship(
        "Node",
        back_populates="roadmap",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Node(Base):
    """Node model."""

    __tablename__ = "nodes"

    id = Column(SA_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(200), nullable=False)
    description = Column(String, nullable=False)
    content = Column(String, nullable=True)
    order = Column(Integer, nullable=False, default=0)
    roadmap_id = Column(
        SA_UUID(as_uuid=True),
        ForeignKey("roadmaps.id", ondelete="CASCADE"),
        nullable=False,
    )
    status = Column(
        String(20),
        nullable=False,
        default="not_started",
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    roadmap = relationship("Roadmap", back_populates="nodes")
    progress = relationship(
        "Progress",
        back_populates="node",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    prerequisites = relationship(
        "Node",
        secondary=node_prerequisites,
        primaryjoin=id == node_prerequisites.c.node_id,
        secondaryjoin=id == node_prerequisites.c.prerequisite_id,
        backref="dependents",
        lazy="selectin",
    )

    def set_status(self, value: str) -> None:
        """Set the node status.

        Args:
            value: The status value to set

        Valid status values are:
        - not_started
        - in_progress
        - completed
        """
        valid_statuses = ["not_started", "in_progress", "completed"]
        if value not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        self.status = value
