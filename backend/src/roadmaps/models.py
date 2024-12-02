import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as SA_UUID
from sqlalchemy.orm import relationship

from src.database.core import Base


class Roadmap(Base):  # type: ignore[misc]
    """Roadmap model."""

    __tablename__ = "roadmaps"

    id = Column(SA_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    description = Column(String)
    skill_level: Column[str] = Column(  # type annotation added
        Enum("beginner", "intermediate", "advanced", name="skill_level_enum"),
        nullable=False,
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    nodes = relationship("Node", back_populates="roadmap", lazy="selectin")


class Node(Base):  # type: ignore[misc]
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
    status = Column(String, nullable=False)

    roadmap = relationship("Roadmap", back_populates="nodes")
    prerequisites = relationship(
        "Node",
        secondary="node_prerequisites",
        primaryjoin=id == "node_prerequisites.c.node_id",
        secondaryjoin=id == "node_prerequisites.c.prerequisite_id",
        backref="dependents",
    )

    def set_status(self, value: str) -> None:
        """Set the node status.

        Parameters
        ----------
        value : str
            The status value to set
        """
        # Use expression.set() for SQLAlchemy Column assignment
        self.status = value  # type: ignore[assignment]
