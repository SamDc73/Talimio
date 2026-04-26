
import uuid
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


AssistantConversationStatus = Literal["regular", "archived"]
AssistantConversationContextType = Literal["book", "video", "course"]
AssistantActiveProbeStatus = Literal["active", "answered", "expired"]


class AssistantConversation(Base):
    """Assistant conversation metadata owned by a single user."""

    __tablename__ = "assistant_conversations"
    __table_args__ = (
        CheckConstraint("status IN ('regular', 'archived')", name="assistant_conversations_status_check"),
        CheckConstraint(
            "context_type IS NULL OR context_type IN ('book', 'video', 'course')",
            name="assistant_conversations_context_type_check",
        ),
        Index("assistant_conversations_user_id_updated_at_idx", "user_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AssistantConversationStatus] = mapped_column(
        String(20), nullable=False, default="regular", server_default="regular"
    )
    context_type: Mapped[AssistantConversationContextType | None] = mapped_column(String(20), nullable=True)
    context_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    context_meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    head_message_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    history_items: Mapped[list[AssistantConversationHistoryItem]] = relationship(
        "AssistantConversationHistoryItem",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    active_probes: Mapped[list[AssistantActiveProbe]] = relationship(
        "AssistantActiveProbe",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class AssistantActiveProbe(Base):
    """Hidden grading state for one chat-generated concept probe."""

    __tablename__ = "assistant_active_probes"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'answered', 'expired')", name="assistant_active_probes_status_check"),
        Index("assistant_active_probes_user_thread_idx", "user_id", "conversation_id", "status"),
        Index("assistant_active_probes_user_concept_idx", "user_id", "course_id", "concept_id", text("created_at DESC")),
        Index(
            "assistant_active_probes_one_active_per_thread_concept_idx",
            "user_id",
            "conversation_id",
            "course_id",
            "concept_id",
            unique=True,
            postgresql_where=text("status = 'active' AND conversation_id IS NOT NULL"),
        ),
        Index(
            "assistant_active_probes_one_active_per_thread_lesson_idx",
            "user_id",
            "conversation_id",
            "course_id",
            "lesson_id",
            unique=True,
            postgresql_where=text("status = 'active' AND conversation_id IS NOT NULL AND lesson_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("assistant_conversations.id", ondelete="CASCADE"),
        nullable=True,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_answer: Mapped[str] = mapped_column(Text, nullable=False)
    answer_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    hints: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    structure_signature: Mapped[str] = mapped_column(Text, nullable=False)
    predicted_p_correct: Mapped[float] = mapped_column(Float, nullable=False)
    target_probability: Mapped[float] = mapped_column(Float, nullable=False)
    target_low: Mapped[float] = mapped_column(Float, nullable=False)
    target_high: Mapped[float] = mapped_column(Float, nullable=False)
    core_model: Mapped[str] = mapped_column(Text, nullable=False)
    practice_context: Mapped[str] = mapped_column(String(40), nullable=False, default="chat", server_default="chat")
    status: Mapped[AssistantActiveProbeStatus] = mapped_column(
        String(20), nullable=False, default="active", server_default="active"
    )
    answered_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    answer_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    conversation: Mapped[AssistantConversation | None] = relationship(
        "AssistantConversation",
        back_populates="active_probes",
    )


class AssistantConversationHistoryItem(Base):
    """Append-only assistant-ui conversation history item."""

    __tablename__ = "assistant_conversation_history_items"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "aui_message_id",
            name="assistant_conv_hist_conv_id_msg_id_key",
        ),
        Index("assistant_conv_hist_conv_id_seq_idx", "conversation_id", "seq"),
        Index(
            "assistant_conv_hist_conv_id_parent_msg_idx",
            "conversation_id",
            "parent_aui_message_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("assistant_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), nullable=False)
    aui_message_id: Mapped[str] = mapped_column(Text, nullable=False)
    parent_aui_message_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    run_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    inserted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    conversation: Mapped[AssistantConversation] = relationship("AssistantConversation", back_populates="history_items")
