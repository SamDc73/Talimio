from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class Book(Base):
    """Model for books."""

    __tablename__ = "books"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(500), nullable=True)
    author: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    isbn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)  # pdf, epub
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # in bytes
    total_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cover_image_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    publication_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    table_of_contents: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    progress_records: Mapped[list["BookProgress"]] = relationship(
        "BookProgress",
        back_populates="book",
        cascade="all, delete-orphan",
    )


class BookProgress(Base):
    """Model for tracking reading progress."""

    __tablename__ = "book_progress"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    book_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("books.id"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # For future user support
    current_page: Mapped[int] = mapped_column(Integer, default=1)
    total_pages_read: Mapped[int] = mapped_column(Integer, default=0)
    progress_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    reading_time_minutes: Mapped[int] = mapped_column(Integer, default=0)
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="not_started")  # not_started, reading, completed, paused
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    bookmarks: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string of page numbers/locations
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    book: Mapped["Book"] = relationship("Book", back_populates="progress_records")
