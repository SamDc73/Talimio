"""SQLAlchemy models for courses, lessons, and adaptive concept scheduling."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as SA_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


_DEFAULT_LEARNER_PROFILE = {
    "learning_speed": 1.0,
    "retention_rate": 0.8,
    "success_rate": 0.5,
    "semantic_sensitivity": 1.0,
}


class Course(Base):
    """Persisted courses owned by a specific user."""

    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = mapped_column(SA_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(SA_UUID(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    setup_commands: Mapped[str | None] = mapped_column(Text, nullable=True)
    adaptive_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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

    lessons: Mapped[list[Lesson]] = relationship(
        "Lesson",
        back_populates="course",
        cascade="all, delete-orphan",
    )
    documents: Mapped[list[CourseDocument]] = relationship(
        "CourseDocument",
        back_populates="course",
        cascade="all, delete-orphan",
    )
    concept_assignments: Mapped[list[CourseConcept]] = relationship(
        "CourseConcept",
        back_populates="course",
        cascade="all, delete-orphan",
    )


class Lesson(Base):
    """Persisted lessons tied to a course."""

    __tablename__ = "lessons"

    id: Mapped[uuid.UUID] = mapped_column(SA_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        SA_UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    module_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    module_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
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

    course: Mapped[Course] = relationship("Course", back_populates="lessons")


class CourseDocument(Base):
    """Documents attached to courses for reference and RAG ingestion."""

    __tablename__ = "course_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[uuid.UUID] = mapped_column(
        SA_UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_type: Mapped[str | None] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str | None] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(String(500))
    crawl_date: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(UTC))
    processed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    embedded_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="pending")

    course: Mapped[Course] = relationship("Course", back_populates="documents")


class Concept(Base):
    """Concept nodes that make up a course DAG."""

    __tablename__ = "concepts"
    __table_args__ = (
        Index("idx_concepts_slug", "slug", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(SA_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector, nullable=True)
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

    course_links: Mapped[list[CourseConcept]] = relationship(
        "CourseConcept",
        back_populates="concept",
        cascade="all, delete-orphan",
    )
    prerequisites: Mapped[list[ConceptPrerequisite]] = relationship(
        "ConceptPrerequisite",
        back_populates="concept",
        cascade="all, delete-orphan",
        foreign_keys="ConceptPrerequisite.concept_id",
    )
    required_for: Mapped[list[ConceptPrerequisite]] = relationship(
        "ConceptPrerequisite",
        back_populates="prerequisite",
        cascade="all, delete-orphan",
        foreign_keys="ConceptPrerequisite.prereq_id",
    )
    user_states: Mapped[list[UserConceptState]] = relationship(
        "UserConceptState",
        back_populates="concept",
        cascade="all, delete-orphan",
    )


class ConceptPrerequisite(Base):
    """Directed prerequisite edge between two concepts."""

    __tablename__ = "concept_prerequisites"
    __table_args__ = (
        PrimaryKeyConstraint("concept_id", "prereq_id"),
        CheckConstraint("concept_id <> prereq_id", name="ck_concept_prereq_no_self"),
    )

    concept_id: Mapped[uuid.UUID] = mapped_column(
        SA_UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
    )
    prereq_id: Mapped[uuid.UUID] = mapped_column(
        SA_UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
    )

    concept: Mapped[Concept] = relationship(
        "Concept",
        foreign_keys=[concept_id],
        back_populates="prerequisites",
    )
    prerequisite: Mapped[Concept] = relationship(
        "Concept",
        foreign_keys=[prereq_id],
        back_populates="required_for",
    )


class CourseConcept(Base):
    """Association table linking courses to their concept graph."""

    __tablename__ = "course_concepts"
    __table_args__ = (
        UniqueConstraint("course_id", "concept_id", name="uq_course_concept"),
    )

    course_id: Mapped[uuid.UUID] = mapped_column(
        SA_UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        primary_key=True,
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        SA_UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    order_hint: Mapped[int | None] = mapped_column(Integer, nullable=True)

    course: Mapped[Course] = relationship("Course", back_populates="concept_assignments")
    concept: Mapped[Concept] = relationship("Concept", back_populates="course_links")


class ConceptSimilarity(Base):
    """Symmetric confusion risk between two concepts."""

    __tablename__ = "concept_similarities"
    __table_args__ = (
        PrimaryKeyConstraint("concept_a_id", "concept_b_id"),
        CheckConstraint("concept_a_id <> concept_b_id", name="ck_concept_similarity_distinct"),
    )

    concept_a_id: Mapped[uuid.UUID] = mapped_column(
        SA_UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
    )
    concept_b_id: Mapped[uuid.UUID] = mapped_column(
        SA_UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
    )
    similarity: Mapped[float] = mapped_column(Float, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class UserConceptState(Base):
    """Learner-specific mastery and scheduling state for a concept."""

    __tablename__ = "user_concept_state"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "concept_id"),
        Index("idx_user_concept_state_user", "user_id"),
        Index("idx_user_concept_state_next_review", "next_review_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        SA_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        SA_UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
    )
    s_mastery: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    exposures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    learner_profile: Mapped[dict[str, float]] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: dict(_DEFAULT_LEARNER_PROFILE),
    )

    concept: Mapped[Concept] = relationship("Concept", back_populates="user_states")


class ProbeEvent(Base):
    """Recorded learner probe for scheduling analytics."""

    __tablename__ = "probe_events"
    __table_args__ = (
        Index("idx_probe_events_user_ts", "user_id", "ts"),
    )

    id: Mapped[uuid.UUID] = mapped_column(SA_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        SA_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        SA_UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    review_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    context_tag: Mapped[str | None] = mapped_column(String(120), nullable=True)
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


__all__ = [
    "Concept",
    "ConceptPrerequisite",
    "ConceptSimilarity",
    "Course",
    "CourseConcept",
    "CourseDocument",
    "Lesson",
    "ProbeEvent",
    "UserConceptState",
]
