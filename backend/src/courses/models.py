"""SQLAlchemy models for the unified courses API.

This module contains all models related to courses, lessons, and document management.
Based on the actual working roadmaps.bck models to match database schema.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    TIMESTAMP,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as SA_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


# Main Course Model (formerly Roadmap) - matches actual database schema
class Course(Base):
    """Model for courses (formerly roadmaps)."""

    __tablename__ = "roadmaps"

    id: Mapped[uuid.UUID] = mapped_column(SA_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(SA_UUID(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array of tags
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rag_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # RAG integration flag
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    nodes: Mapped[list["CourseModule"]] = relationship("CourseModule", back_populates="roadmap")
    documents: Mapped[list["CourseDocument"]] = relationship("CourseDocument", back_populates="roadmap")


# Course Module Model (formerly Node) - matches actual database schema
class CourseModule(Base):
    """Model for course modules (formerly nodes)."""

    __tablename__ = "nodes"

    id: Mapped[uuid.UUID] = mapped_column(SA_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    roadmap_id: Mapped[uuid.UUID] = mapped_column(SA_UUID(as_uuid=True), ForeignKey("roadmaps.id"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="not_started")
    completion_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(SA_UUID(as_uuid=True), ForeignKey("nodes.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships - keep original names
    roadmap: Mapped["Course"] = relationship("Course", back_populates="nodes")


# Lesson Model - simplified for now
class Lesson(Base):
    """Model for lessons."""

    __tablename__ = "lessons"

    id: Mapped[uuid.UUID] = mapped_column(SA_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    roadmap_id: Mapped[uuid.UUID] = mapped_column(SA_UUID(as_uuid=True), ForeignKey("roadmaps.id"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0)  # Keep consistent naming
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


# Progress Model - matches actual database schema
class LessonProgress(Base):
    """Model for lesson progress tracking."""

    __tablename__ = "progress"

    id: Mapped[uuid.UUID] = mapped_column(SA_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id: Mapped[str] = mapped_column(String)  # Actually stores module_id - varchar in DB
    lesson_id: Mapped[str | None] = mapped_column(String, nullable=True)  # varchar in DB
    status: Mapped[str] = mapped_column(String(50), default="not_started")
    user_id: Mapped[uuid.UUID] = mapped_column(SA_UUID(as_uuid=True))  # Fixed: Use UUID type to match database
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


# Document Management Models for RAG - from working backup
class CourseDocument(Base):
    """Model for course documents (formerly RoadmapDocument)."""

    __tablename__ = "roadmap_documents"  # Actual database table name

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[uuid.UUID] = mapped_column(
        SA_UUID, ForeignKey("roadmaps.id", ondelete="CASCADE"), name="roadmap_id"
    )  # Maps to roadmap_id column
    document_type: Mapped[str | None] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str | None] = mapped_column(String(500))
    url: Mapped[str | None] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(String(500))
    crawl_date: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    parsed_content: Mapped[str | None] = mapped_column(Text)
    doc_metadata: Mapped[dict | None] = mapped_column(
        JSON, name="metadata"
    )  # Use name parameter to map to database column
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(UTC))
    processed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    embedded_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # 'pending', 'processing', 'embedded', 'failed'

    # Relationships
    roadmap: Mapped["Course"] = relationship(
        "Course", back_populates="documents", foreign_keys="CourseDocument.course_id"
    )

    # Alias property for new naming convention
    @property
    def course(self) -> "Course":
        """Alias for roadmap to support course naming."""
        return self.roadmap


# Create aliases for backward compatibility
Roadmap = Course
RoadmapDocument = CourseDocument
Node = CourseModule


# Re-export all models
__all__ = [
    "Course",
    "CourseDocument",
    "CourseModule",
    "Lesson",
    "LessonProgress",
    "Node",
    "Roadmap",
    "RoadmapDocument",
]
