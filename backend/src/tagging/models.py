"""Database models for the tagging system."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class Tag(Base):
    """Tag model for categorizing content."""

    __tablename__ = "tags"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)  # hex color
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    associations: Mapped[list["TagAssociation"]] = relationship(
        "TagAssociation",
        back_populates="tag",
        cascade="all, delete-orphan",
    )


class TagAssociation(Base):
    """Association between tags and content items."""

    __tablename__ = "tag_associations"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    tag_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), ForeignKey("tags.id"), nullable=False)
    content_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False, index=True)
    content_type: Mapped[str] = mapped_column(String(20), nullable=False)  # book, video, roadmap
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0)
    auto_generated: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    tag: Mapped["Tag"] = relationship("Tag", back_populates="associations")
