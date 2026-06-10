"""SQLAlchemy models for canonical durable user profile memory."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base
from src.user import models as _user_models  # noqa: F401  # registers the users table these FKs resolve against


class UserProfileSlot(Base):
    """One durable profile preference; one active row per user+slot."""

    __tablename__ = "user_profile_slots"
    __table_args__ = (
        CheckConstraint("source IN ('manual', 'inferred', 'legacy_migration')", name="source_allowed"),
        Index(
            "user_profile_slots_user_id_slot_active_key",
            "user_id",
            "slot",
            unique=True,
            postgresql_where="is_active",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    slot: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_evidence_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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


class UserMemoryWatermark(Base):
    """High-water mark of conversation-history seq already evaluated for a user."""

    __tablename__ = "user_memory_watermarks"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    last_processed_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class UserProfileSlotEvent(Base):
    """Provenance/evidence log row for an inferred profile write decision."""

    __tablename__ = "user_profile_slot_events"
    __table_args__ = (
        CheckConstraint("op IN ('set', 'clear', 'ignore', 'defer')", name="op_allowed"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        CheckConstraint(
            "status IN ('applied', 'noop', 'rejected_stale', 'rejected_manual', 'shadow')",
            name="status_allowed",
        ),
        Index("user_profile_slot_events_user_id_created_at_idx", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    slot: Mapped[str] = mapped_column(Text, nullable=False)
    op: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    message_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_message_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    redacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
