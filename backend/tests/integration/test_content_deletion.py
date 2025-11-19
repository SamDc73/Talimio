"""Hard-delete tests for /api/v1/content/{type}/{id}.

High-level, endpoint-first tests that mimic user flows:
- Create content via public endpoints (book upload, video add, course create)
- Attach tags via API and insert a small RAG footprint
- Delete via unified content endpoint and assert full cleanup
"""

import io
import json
import os
import tempfile
import uuid
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.books.models import Book
from src.courses.models import Course, CourseDocument
from src.videos.models import Video
from src.auth.config import DEFAULT_USER_ID
from tests.fixtures.auth_modes import AuthMode


# Run these tests in both auth modes
pytestmark = pytest.mark.parametrize("auth_mode", [AuthMode.SINGLE_USER, AuthMode.MULTI_USER], indirect=True)


def _client_user_id(client) -> str:
    """Get the expected user_id for the given ModeAwareClient as a string."""
    try:
        return client.expected_user_id
    except Exception:
        return str(DEFAULT_USER_ID)


async def _insert_rag_chunk(
    session: AsyncSession, *, doc_id: UUID, doc_type: str, metadata: dict | None = None
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO rag_document_chunks (doc_id, doc_type, chunk_index, content, metadata)
            VALUES (:doc_id, :doc_type, 0, 'chunk', CAST(:metadata AS jsonb))
            """
        ),
        {"doc_id": str(doc_id), "doc_type": doc_type, "metadata": json.dumps(metadata or {})},
    )
    await session.commit()


async def _put_tags(client, content_type: str, content_id: UUID, tags: list[str]) -> None:
    resp = await client.put(f"/api/v1/tags/{content_type}/{content_id}/tags", json={"tags": tags})
    assert resp.status_code in (200, 201)


@pytest.mark.asyncio
async def test_delete_book_hard(client_factory, db_session: AsyncSession) -> None:
    # Create book directly in DB (book upload path uses a separate session factory)
    client = await client_factory()
    book_id = uuid.uuid4()
    await db_session.execute(
        text(
            """
            INSERT INTO books (id, user_id, title, author, total_pages, file_type, file_path, file_size, rag_status, archived)
            VALUES (:id, :uid, 'Test Book', 'Tester', 10, 'pdf', 'books/test-user/test.pdf', 1234, 'pending', false)
            """
        ),
        {"id": str(book_id), "uid": _client_user_id(client)},
    )
    await db_session.commit()

    # Insert minimal RAG footprint and a tag via API
    await _insert_rag_chunk(db_session, doc_id=book_id, doc_type="book")
    unique_tag = f"t-{uuid.uuid4()}"
    await _put_tags(client, "book", book_id, [unique_tag])

    # Delete via unified endpoint
    del_resp = await client.delete(f"/api/v1/content/book/{book_id}")
    assert del_resp.status_code in (200, 204)

    # Primary row gone
    assert (await db_session.execute(select(Book).where(Book.id == book_id))).scalar_one_or_none() is None

    # RAG chunks gone
    count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM rag_document_chunks WHERE doc_id = :id AND doc_type = 'book'"),
            {"id": str(book_id)},
        )
    ).scalar()
    assert count == 0

    # No tag associations and orphan tags pruned
    ta_count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM tag_associations WHERE content_id = :id AND content_type = 'book'"),
            {"id": str(book_id)},
        )
    ).scalar()
    assert ta_count == 0

    orphan_count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM tags t LEFT JOIN tag_associations ta ON ta.tag_id = t.id WHERE ta.id IS NULL"),
        )
    ).scalar()
    assert orphan_count == 0


@pytest.mark.asyncio
async def test_delete_video_hard(client_factory, db_session: AsyncSession) -> None:
    # Create video via API
    client = await client_factory()
    resp = await client.post("/api/v1/videos", json={"url": "https://www.youtube.com/watch?v=vid123"})
    assert resp.status_code == 201, resp.text
    video_id = UUID(resp.json()["id"])

    # Insert minimal RAG footprint and a tag via API
    await _insert_rag_chunk(db_session, doc_id=video_id, doc_type="video")
    unique_tag = f"t-{uuid.uuid4()}"
    await _put_tags(client, "video", video_id, [unique_tag])

    # Sanity
    assert (await db_session.execute(select(Video).where(Video.id == video_id))).scalar_one_or_none() is not None

    # Delete via unified endpoint
    del_resp = await client.delete(f"/api/v1/content/youtube/{video_id}")
    assert del_resp.status_code in (200, 204)

    # Primary row gone
    assert (await db_session.execute(select(Video).where(Video.id == video_id))).scalar_one_or_none() is None

    # RAG chunks gone
    count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM rag_document_chunks WHERE doc_id = :id AND doc_type = 'video'"),
            {"id": str(video_id)},
        )
    ).scalar()
    assert count == 0

    # No tag associations and orphan tags pruned
    ta_count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM tag_associations WHERE content_id = :id AND content_type = 'video'"),
            {"id": str(video_id)},
        )
    ).scalar()
    assert ta_count == 0

    orphan_count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM tags t LEFT JOIN tag_associations ta ON ta.tag_id = t.id WHERE ta.id IS NULL"),
        )
    ).scalar()
    assert orphan_count == 0


@pytest.mark.asyncio
async def test_delete_course_hard(client_factory, db_session: AsyncSession, tmp_path) -> None:
    # Create course directly in DB (avoid AI generation shape differences)
    client = await client_factory()
    course_id = uuid.uuid4()
    await db_session.execute(
        text(
            """
            INSERT INTO courses (id, user_id, title, description, adaptive_enabled, archived, created_at, updated_at)
            VALUES (:id, :uid, 'Test Course', 'Desc', false, false, NOW(), NOW())
            """
        ),
        {"id": str(course_id), "uid": _client_user_id(client)},
    )
    # Add lessons
    await db_session.execute(
        text(
            """
            INSERT INTO lessons (id, course_id, title, description, content, "order", created_at, updated_at)
            VALUES (:l1, :cid, 'L1', '', '...', 0, NOW(), NOW()), (:l2, :cid, 'L2', '', '...', 0, NOW(), NOW())
            """
        ),
        {"l1": str(uuid.uuid4()), "l2": str(uuid.uuid4()), "cid": str(course_id)},
    )

    # Add a course document source file directly (avoid heavy Unstructured dependency)
    fd, tmp_file = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    Path(tmp_file).write_bytes(b"dummy")
    await db_session.execute(
        text(
            """
            INSERT INTO course_documents (course_id, document_type, title, file_path, status, created_at)
            VALUES (:cid, 'file', 'Doc', :fp, 'pending', NOW())
            """
        ),
        {"cid": str(course_id), "fp": tmp_file},
    )
    await db_session.commit()

    # Insert minimal course RAG footprint and a tag via API
    await _insert_rag_chunk(db_session, doc_id=uuid.uuid4(), doc_type="course", metadata={"course_id": str(course_id)})
    unique_tag = f"t-{uuid.uuid4()}"
    await _put_tags(client, "course", course_id, [unique_tag])

    # Sanity: course exists and course_document exists
    assert (await db_session.execute(select(Course).where(Course.id == course_id))).scalar_one_or_none() is not None
    doc_row = (
        await db_session.execute(select(CourseDocument).where(CourseDocument.course_id == course_id))
    ).scalar_one()
    assert doc_row.file_path and Path(doc_row.file_path).exists()

    # Delete via unified endpoint
    del_resp = await client.delete(f"/api/v1/content/course/{course_id}")

    assert del_resp.status_code in (200, 204)

    # Primary row gone
    assert (await db_session.execute(select(Course).where(Course.id == course_id))).scalar_one_or_none() is None

    # Lessons gone (cascade), documents gone (cascade)
    lesson_count = (
        await db_session.execute(text("SELECT COUNT(*) FROM lessons WHERE course_id = :cid"), {"cid": str(course_id)})
    ).scalar()
    assert lesson_count == 0
    doc_count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM course_documents WHERE course_id = :cid"), {"cid": str(course_id)}
        )
    ).scalar()
    assert doc_count == 0

    # Course RAG chunks gone
    rag_count = (
        await db_session.execute(
            text(
                "SELECT COUNT(*) FROM rag_document_chunks WHERE doc_type = 'course' AND metadata->>'course_id' = :cid"
            ),
            {"cid": str(course_id)},
        )
    ).scalar()
    assert rag_count == 0

    # No tag associations and orphan tags pruned
    ta_count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM tag_associations WHERE content_id = :cid AND content_type = 'course'"),
            {"cid": str(course_id)},
        )
    ).scalar()
    assert ta_count == 0

    orphan_count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM tags t LEFT JOIN tag_associations ta ON ta.tag_id = t.id WHERE ta.id IS NULL"),
        )
    ).scalar()
    assert orphan_count == 0

    # Source file unlinked
    assert not Path(doc_row.file_path).exists()


@pytest.mark.asyncio
async def test_delete_nonexistent(client_factory) -> None:
    client = await client_factory()
    missing_id = uuid.uuid4()
    resp = await client.delete(f"/api/v1/content/youtube/{missing_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_fails_for_non_owner(client_factory, db_session: AsyncSession) -> None:
    # Owner creates a video
    owner = await client_factory("owner@test.com")
    if owner.auth_mode != AuthMode.MULTI_USER:
        pytest.skip("Non-owner case only applies to multi-user mode")

    resp = await owner.post("/api/v1/videos", json={"url": "https://youtu.be/abc123"})
    assert resp.status_code == 201, resp.text
    video_id = UUID(resp.json()["id"])

    # Attacker attempts delete
    attacker = await client_factory("attacker@test.com")
    del_resp = await attacker.delete(f"/api/v1/content/youtube/{video_id}")
    assert del_resp.status_code == 404

    # Still exists
    assert (await db_session.execute(select(Video).where(Video.id == video_id))).scalar_one_or_none() is not None
