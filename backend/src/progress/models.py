"""Progress models for tracking lesson completion."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID

from src.database.base import Base


class Progress(Base):
    """Progress model for tracking lesson completion status."""

    __tablename__ = "progress"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lesson_id = Column(String, nullable=False, index=True)
    course_id = Column(String, nullable=False, index=True)
    status = Column(
        String,
        nullable=False,
        default="not_started",
        # Ensure status is one of the allowed values
        # not_started, in_progress, done
    )
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        """Return string representation of the progress."""
        return f"<Progress(id={self.id}, lesson_id={self.lesson_id}, status={self.status})>"
