from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as POSTGRES_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


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

    id: Mapped[uuid.UUID] = mapped_column(POSTGRES_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(POSTGRES_UUID(as_uuid=True), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="regular", server_default="regular")
    context_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    context_id: Mapped[uuid.UUID | None] = mapped_column(POSTGRES_UUID(as_uuid=True), nullable=True)
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

    id: Mapped[uuid.UUID] = mapped_column(POSTGRES_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        POSTGRES_UUID(as_uuid=True),
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
