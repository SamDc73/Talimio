"""Procrastinate tasks for post-upload ingestion of books and videos.

Metadata, embeddings, tags, chapters, and transcripts used to run as FastAPI
``BackgroundTasks`` after the response. That keeps the API process busy after
requests end, which is exactly what request-based Cloud Run billing throttles.
As jobs they run on the worker instead, and survive an instance being killed.
"""

from __future__ import annotations

import uuid

from src.jobs.app import QUEUE_INGESTION, job_app


@job_app.task(name="ingestion.process_book", queue=QUEUE_INGESTION)
async def process_book(book_id: str, user_id: str) -> None:
    """Extract metadata, embed, and tag one newly created book."""
    from src.books.facade import BooksFacade
    from src.database.session import async_session_maker

    async with async_session_maker() as session:
        await BooksFacade(session).ingest_book_background(uuid.UUID(book_id), uuid.UUID(user_id))


@job_app.task(name="ingestion.process_video", queue=QUEUE_INGESTION)
async def process_video(video_id: str, user_id: str) -> None:
    """Tag, extract chapters, and store the transcript of one newly created video."""
    from src.videos.service import run_video_ingestion

    await run_video_ingestion(uuid.UUID(video_id), uuid.UUID(user_id))
