"""SQLAlchemy models for pedagogical memory (course-scoped teaching state)."""

import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from pydantic import JsonValue
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
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


class StudentCard(Base):
    """One labeled plain-text pedagogical summary block per user+course."""

    __tablename__ = "student_cards"
    __table_args__ = (UniqueConstraint("user_id", "course_id", name="student_cards_user_id_course_id_key"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    card_text: Mapped[str] = mapped_column(Text, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Explicit learner forget: soft-deleted cards are skipped at read time and
    # reborn as a fresh skeleton (same row) on next use.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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


class StudentCardRevision(Base):
    """Append-only full-text snapshot per card edit (provenance + rebuild substrate)."""

    __tablename__ = "student_card_revisions"
    __table_args__ = (UniqueConstraint("card_id", "revision", name="student_card_revisions_card_id_revision_key"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    card_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("student_cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    card_text: Mapped[str] = mapped_column(Text, nullable=False)
    tool_call: Mapped[dict[str, JsonValue]] = mapped_column(JSONB, nullable=False, default=dict)
    evidence_refs: Mapped[list[JsonValue]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class PedagogyWatermark(Base):
    """High-water mark of evidence ``created_at`` already consolidated for a learner-course pair."""

    __tablename__ = "pedagogy_watermarks"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        primary_key=True,
    )
    last_processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime(1970, 1, 1, tzinfo=UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class PedagogicalNote(Base):
    """One distilled, retrieval-worthy pedagogical fact with provenance.

    The note carries the searchable claim; verbatim_quote keeps a short raw
    source excerpt because the lexical leg ranks learner phrasing better than
    distilled text. No ANN index: per-user corpora are small, so the exact
    cosine scan is perfect-recall.
    """

    __tablename__ = "pedagogical_notes"
    __table_args__ = (
        CheckConstraint(
            "source_kind IN ('lesson_feedback_event', 'teaching_event', 'updater_reflection')",
            name="source_kind_allowed",
        ),
        Index("pedagogical_notes_user_id_idx", "user_id"),
        Index("pedagogical_notes_user_id_course_id_idx", "user_id", "course_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=True,
    )
    note: Mapped[str] = mapped_column(Text, nullable=False)
    scene_trace: Mapped[str] = mapped_column(Text, nullable=False)
    verbatim_quote: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_kind: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class TeachingEvent(Base):
    """Append-only pedagogical evidence: what was shown and how the learner responded."""

    __tablename__ = "teaching_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('lesson_version_shown', 'check_answered', 'lesson_regenerated', "
            "'lesson_completed', 'delayed_outcome', 'preference_stated')",
            name="event_type_allowed",
        ),
        Index("teaching_events_user_id_course_id_occurred_at_idx", "user_id", "course_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Intentionally no FKs below: events must survive lesson/version deletion as evidence.
    lesson_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    lesson_version_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    concept_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    strategy_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    window_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hints_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict[str, JsonValue]] = mapped_column(JSONB, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
