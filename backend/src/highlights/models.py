"""
SQLAlchemy models for highlights feature.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base


class Highlight(Base):
    """Model for storing text highlights across different content types."""

    __tablename__ = "highlights"

    id: Mapped["UUID"] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped["UUID"] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content_id: Mapped["UUID"] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    highlight_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), onupdate=text("NOW()")
    )

    __table_args__ = (CheckConstraint("content_type IN ('book', 'course', 'video')", name="valid_content_type"),)
