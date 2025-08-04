from __future__ import annotations

import uuid
from datetime import datetime  # noqa: TC003
from uuid import UUID as UUID_TYPE

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class Video(Base):
    """Video model for storing YouTube videos."""

    __tablename__ = "videos"

    id: Mapped[UUID_TYPE] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    youtube_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    channel: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_id: Mapped[str] = mapped_column(String(50), nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)  # Duration in seconds
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array stored as text
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)  # Full transcript content
    transcript_data: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )  # Structured transcript data with segments (JSONB)
    transcript_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # RAG processing status
    rag_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending, processing, completed, failed
    rag_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Chapter extraction status
    chapters_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending, processing, completed, failed
    chapters_extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Archive status
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    chapters: Mapped[list[VideoChapter]] = relationship(
        "VideoChapter",
        back_populates="video",
        cascade="all, delete-orphan",
    )
    progress_records: Mapped[list[VideoProgress]] = relationship(
        "VideoProgress",
        back_populates="video",
        cascade="all, delete-orphan",
    )


class VideoChapter(Base):
    """Model for video chapters."""

    __tablename__ = "video_chapters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    start_time: Mapped[int | None] = mapped_column(Integer, nullable=True)  # in seconds
    end_time: Mapped[int | None] = mapped_column(Integer, nullable=True)  # in seconds
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_started")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    video: Mapped[Video] = relationship("Video", back_populates="chapters")


class VideoProgress(Base):
    """Model for tracking user-specific video progress."""

    __tablename__ = "video_progress"

    id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[UUID_TYPE] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID_TYPE] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    last_position: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # Position in seconds
    completion_percentage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_watched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    video: Mapped[Video] = relationship("Video", back_populates="progress_records")
