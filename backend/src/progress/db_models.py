"""Database models for progress tracking."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, Column, DateTime, Float, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from src.database.base import Base


class UserProgress(Base):
    """User progress tracking for all content types."""
    
    __tablename__ = "user_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "content_id", name="uq_user_content"),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    content_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    content_type = Column(String(50), nullable=False, index=True)
    progress_percentage = Column(Float, nullable=False, default=0.0)
    progress_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))