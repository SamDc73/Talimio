"""SQLAlchemy models for pedagogical memory (course-scoped teaching state)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base


class CourseTeachingProfile(Base):
    """Durable course-level teaching preferences; one row per course+source."""

    __tablename__ = "course_teaching_profiles"
    __table_args__ = (
        CheckConstraint("source IN ('explicit', 'inferred')", name="source_allowed"),
        UniqueConstraint("course_id", "source", name="course_teaching_profiles_course_id_source_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    pace_preference: Mapped[str | None] = mapped_column(Text, nullable=True)
    example_style: Mapped[str | None] = mapped_column(Text, nullable=True)
    quiz_density_preference: Mapped[str | None] = mapped_column(Text, nullable=True)
    visual_preference: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_preference: Mapped[str | None] = mapped_column(Text, nullable=True)
    tone_preference: Mapped[str | None] = mapped_column(Text, nullable=True)
    avoid_list: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
