"""Regression test: deleting a course should cascade-delete lessons and documents.

This ensures our DB-level cascades and delete pipeline keep the database clean.
"""

import os
import tempfile
import uuid
from pathlib import Path
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.config import DEFAULT_USER_ID
from src.courses.models import Course, CourseDocument, Lesson


@pytest_asyncio.fixture
async def user_id() -> UUID:
    return (
        DEFAULT_USER_ID
        if os.getenv("AUTH_PROVIDER", "none") == "none"
        else UUID("11111111-1111-1111-1111-111111111111")
    )


@pytest_asyncio.fixture
async def course_with_children(db_session: AsyncSession, user_id: UUID) -> tuple[UUID, str]:
    """Create a course with a couple of lessons and one course document."""
    cid = uuid.uuid4()
    course = Course(id=cid, user_id=user_id, title="Cascade Course", description="Desc")
    db_session.add(course)
    await db_session.commit()

    # Add lessons
    db_session.add_all(
        [
            Lesson(course_id=cid, title="L1", description="", content="..."),
            Lesson(course_id=cid, title="L2", description="", content="..."),
        ]
    )

    # Add a temp file-backed document
    fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    Path(tmp_path).write_bytes(b"test")
    db_session.add(
        CourseDocument(course_id=cid, document_type="file", title="Doc", file_path=tmp_path, status="pending")
    )

    await db_session.commit()

    return cid, tmp_path


@pytest.mark.asyncio
async def test_course_delete_cascades_children(
    client_factory, db_session: AsyncSession, course_with_children: tuple[UUID, str]
) -> None:
    course_id, file_path = course_with_children

    # Pre-checks
    assert (await db_session.execute(select(Course).where(Course.id == course_id))).scalar_one_or_none() is not None
    assert Path(file_path).exists()

    client = await client_factory()
    resp = await client.delete(f"/api/v1/content/course/{course_id}")
    assert resp.status_code in (200, 204)

    # Course gone
    assert (await db_session.execute(select(Course).where(Course.id == course_id))).scalar_one_or_none() is None

    # Lessons gone
    lesson_count = (
        await db_session.execute(text("SELECT COUNT(*) FROM lessons WHERE course_id = :cid"), {"cid": str(course_id)})
    ).scalar()
    assert lesson_count == 0

    # Course documents gone
    doc_count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM course_documents WHERE course_id = :cid"), {"cid": str(course_id)}
        )
    ).scalar()
    assert doc_count == 0

    # Source file unlinked
    assert not Path(file_path).exists()
