import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import TIMESTAMP, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as SA_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


__all__ = ["DocumentChunk", "Node", "Roadmap", "RoadmapDocument"]


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
    tags_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array of tags
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
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
    completion_percentage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
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


class RoadmapDocument(Base):
    """Document attached to a roadmap for RAG processing."""

    __tablename__ = "roadmap_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    roadmap_id: Mapped[uuid.UUID] = mapped_column(SA_UUID, ForeignKey("roadmaps.id", ondelete="CASCADE"))
    document_type: Mapped[str] = mapped_column(String(20))  # 'pdf', 'url'
    title: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    crawl_date: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parsed_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    doc_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    embedded_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # 'pending', 'processing', 'embedded', 'failed'

    # Relationships
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(Base):
    """Text chunk from a document with embeddings for vector search."""

    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("roadmap_documents.id", ondelete="CASCADE"))
    node_id: Mapped[str] = mapped_column(String(255), unique=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    # Note: embedding vector column is handled by pgvector extension directly
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    doc_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)

    # Relationships
    document: Mapped["RoadmapDocument"] = relationship("RoadmapDocument", back_populates="chunks")
