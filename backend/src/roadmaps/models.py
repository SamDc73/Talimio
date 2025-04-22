import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional


if TYPE_CHECKING:
    from .models import Node, Progress, Roadmap, User

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as SA_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.core import Base


__all__ = ["Node", "Roadmap"]

# Association table for node prerequisites (removed, not needed for simple hierarchy)
# node_prerequisites = Table(
#     "node_prerequisites",
#     Base.metadata,
#     Column(
#         "node_id",
#         SA_UUID(as_uuid=True),
#         ForeignKey("nodes.id", ondelete="CASCADE"),
#         primary_key=True,
#     ),
#     Column(
#         "prerequisite_id",
#         SA_UUID(as_uuid=True),
#         ForeignKey("nodes.id", ondelete="CASCADE"),
#         primary_key=True,
#     ),
# )


class Roadmap(Base):
    """Roadmap model."""

    __tablename__ = "roadmaps"

    id: Mapped[uuid.UUID] = mapped_column(SA_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    skill_level: Mapped[str] = mapped_column(
        Enum("beginner", "intermediate", "advanced", name="skill_level_enum"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    # Add user_id foreign key for roadmap ownership
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        SA_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationship to User (owner)
    owner: Mapped["User"] = relationship("User", back_populates="roadmaps", lazy="selectin")

    nodes: Mapped[list["Node"]] = relationship(
        "Node",
        back_populates="roadmap",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Node(Base):
    """Node model."""

    __tablename__ = "nodes"

    id: Mapped[uuid.UUID] = mapped_column(SA_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    label_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str | None] = mapped_column(String, nullable=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    roadmap_id: Mapped[uuid.UUID] = mapped_column(
        SA_UUID(as_uuid=True),
        ForeignKey("roadmaps.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Add parent_id for hierarchy (nullable FK to nodes.id)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        SA_UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_started")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    roadmap: Mapped["Roadmap"] = relationship("Roadmap", back_populates="nodes")
    # Self-referential relationships for hierarchy
    parent: Mapped[Optional["Node"]] = relationship(
        "Node",
        remote_side="Node.id",
        back_populates="children",
        foreign_keys=[parent_id],
        lazy="selectin",
    )
    children: Mapped[list["Node"]] = relationship(
        "Node",
        back_populates="parent",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    # --- REMOVE ALL REFERENCES TO PREREQUISITES ---
    # If any code tries to access node.prerequisites, it should raise AttributeError
    # or be removed from the codebase.
    progress_records: Mapped[list["Progress"]] = relationship(
        "Progress",
        back_populates="node",
        cascade="all, delete-orphan",
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
            msg = f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            raise ValueError(msg)
        self.status = value
