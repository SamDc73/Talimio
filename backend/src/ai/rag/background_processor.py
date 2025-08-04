"""
Unified background processor for RAG pipeline.

This module provides a unified interface for processing content embeddings
in the background, eliminating code duplication between book and video processing.
"""

import logging
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.rag.chunker import ChunkerFactory
from src.ai.rag.ingest import DocumentProcessor
from src.ai.rag.vector_store import VectorStore
from src.ai.rag.video_chunker import VideoTranscriptChunker
from src.books.models import Book
from src.database.session import async_session_maker
from src.storage.factory import get_storage_provider
from src.videos.models import Video, VideoChapter


logger = logging.getLogger(__name__)


# Type variable for content models
ContentModel = TypeVar("ContentModel", Book, Video)


class ContentExtractor:
    """Base class for content extractors."""

    async def extract_content(self, content_id: UUID, session: AsyncSession) -> tuple[str | list[dict], dict[str, Any]]:
        """Extract content and metadata for processing."""
        raise NotImplementedError


class BookContentExtractor(ContentExtractor):
    """Content extractor for books."""

    async def extract_content(self, book_id: UUID, session: AsyncSession) -> tuple[str, dict[str, Any]]:
        """Extract book content from storage."""
        logger.info(f"Starting book content extraction for {book_id}")

        # Get the book record
        result = await session.execute(select(Book).where(Book.id == book_id))
        book = result.scalar_one_or_none()

        if not book:
            msg = f"Book {book_id} not found"
            raise ValueError(msg)

        logger.info(f"Found book: '{book.title}' by {book.author}, file_path='{book.file_path}'")

        # Download file from storage
        logger.info(f"Downloading book file from storage: {book.file_path}")
        storage = get_storage_provider()
        file_content = await storage.download(book.file_path)
        logger.info(f"Downloaded {len(file_content)} bytes from storage")

        # Save to temporary file for processing
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(suffix=Path(book.file_path).suffix, delete=False) as tmp:
                tmp.write(file_content)
                temp_file = tmp.name

            logger.info(f"Saved to temporary file: {temp_file} ({Path(book.file_path).suffix})")

            # Extract text
            document_processor = DocumentProcessor()
            file_type = Path(book.file_path).suffix.lstrip(".")
            logger.info(f"Processing document as type: {file_type}")

            text_content = await document_processor.process_document(temp_file, file_type)

            logger.info(f"Extracted {len(text_content)} characters from book")

            # Prepare metadata
            metadata = {
                "book_id": str(book_id),
                "title": book.title,
                "author": book.author,
                "user_id": str(book.user_id),
            }

            return text_content, metadata

        except Exception as e:
            logger.exception(f"Error extracting book content: {type(e).__name__}: {e!s}")
            raise
        finally:
            # Clean up temp file
            if temp_file and Path(temp_file).exists():
                Path(temp_file).unlink()
                logger.info(f"Cleaned up temporary file: {temp_file}")


class VideoContentExtractor(ContentExtractor):
    """Content extractor for videos."""

    async def extract_content(self, video_uuid: UUID, session: AsyncSession) -> tuple[list[dict] | str, dict[str, Any]]:
        """Extract video transcript content."""
        # Get the video record
        result = await session.execute(select(Video).where(Video.uuid == video_uuid))
        video = result.scalar_one_or_none()

        if not video:
            msg = f"Video {video_uuid} not found"
            raise ValueError(msg)

        # Try to get transcript segments with timestamps first
        transcript_segments = None
        try:
            # Import here to avoid circular imports
            from src.videos.service import VideoService

            service = VideoService()
            # Use public method instead of private one
            transcript_response = await service.get_video_transcript_segments(session, str(video_uuid))
            if transcript_response and transcript_response.segments:
                transcript_segments = [
                    {"start": seg.start_time, "end": seg.end_time, "text": seg.text}
                    for seg in transcript_response.segments
                ]
        except Exception as e:
            logger.warning(f"Failed to extract transcript segments for video {video_uuid}: {e}")

        # Prepare metadata
        metadata = {
            "video_uuid": str(video_uuid),
            "title": video.title,
            "channel": video.channel,
            "user_id": str(video.user_id) if hasattr(video, "user_id") else None,
        }

        # Return segments if available, otherwise plain transcript
        if transcript_segments:
            return transcript_segments, metadata
        # Fallback to plain transcript
        transcript_content = video.transcript
        if not transcript_content:
            # Try to extract it using public method
            try:
                from src.videos.service import VideoService

                service = VideoService()
                transcript_response = await service.get_video_transcript_segments(session, str(video_uuid))
                # Combine segments into plain text
                if transcript_response and transcript_response.segments:
                    transcript_content = " ".join(seg.text for seg in transcript_response.segments)
                    # Save transcript if extracted successfully
                    if transcript_content:
                        video.transcript = transcript_content
                        await session.commit()
            except Exception as e:
                logger.warning(f"Failed to extract transcript for video {video_uuid}: {e}")

        return transcript_content or "", metadata


async def _update_content_status[ContentModel: (Book, Video)](
    content_id: UUID, content_type: str, model_class: type[ContentModel], status: str, error_msg: str | None = None
) -> None:
    """Update content RAG status in database."""
    try:
        async with async_session_maker() as session:
            result = await session.execute(select(model_class).where(model_class.id == content_id))
            content = result.scalar_one_or_none()
            if content:
                content.rag_status = status
                if status == "completed":
                    content.rag_processed_at = datetime.now(UTC)
                elif status == "failed" and hasattr(content, "rag_error") and error_msg:
                    content.rag_error = error_msg
                await session.commit()
                logger.info(f"Updated {content_type} {content_id} status to '{status}'")
    except Exception as e:
        logger.exception(f"Failed to update {content_type} {content_id} status to {status}: {e}")


async def _log_extraction_details(content_type: str, content_id: UUID, extracted_content: str | list[dict]) -> None:
    """Log details about extracted content."""
    if content_type == "book":
        logger.info(f"Extracted {len(extracted_content)} characters from book {content_id}")
    elif content_type == "video":
        if isinstance(extracted_content, list):
            logger.info(f"Extracted {len(extracted_content)} transcript segments from video {content_id}")
        else:
            logger.info(f"Extracted {len(extracted_content)} characters from video {content_id}")


async def _store_content_embeddings(
    session: AsyncSession,
    content_type: str,
    content_id: UUID,
    chunks: list[str] | list[dict],
    metadata: dict[str, Any],
    vector_store: VectorStore,
) -> None:
    """Store content embeddings in vector store."""
    if content_type == "book":
        await vector_store.store_chunks_with_embeddings(session, content_id, content_type, chunks, metadata)
    else:  # video
        await vector_store.store_chunks_with_embeddings(session, content_id, chunks, doc_type=content_type)


async def process_content_rag_background[ContentModel: (Book, Video)](
    content_id: UUID, content_type: str, content_extractor: ContentExtractor, model_class: type[ContentModel]
) -> None:
    """
    Unified background processor for content RAG embeddings.

    Args:
        content_id: UUID of the content to process
        content_type: Type of content ("book" or "video")
        content_extractor: Extractor instance for the content type
        model_class: SQLAlchemy model class for the content
    """
    try:
        logger.info(f"Starting RAG processing for {content_type} {content_id}")

        async with async_session_maker() as session:
            # Get and validate content record
            result = await session.execute(select(model_class).where(model_class.id == content_id))
            content = result.scalar_one_or_none()

            if not content:
                logger.error(f"{content_type.title()} {content_id} not found for RAG processing")
                return

            # Log content details
            logger.info(f"Processing {content_type}: title='{content.title}', user_id={content.user_id}")
            if content_type == "book":
                logger.info(f"Book details: file_path='{content.file_path}', file_type='{content.file_type}'")

            # Update status to processing
            content.rag_status = "processing"
            await session.commit()
            logger.info(f"Set {content_type} {content_id} status to 'processing'")

            # Extract content
            logger.info(f"Extracting content for {content_type} {content_id}")
            extracted_content, metadata = await content_extractor.extract_content(content_id, session)
            await _log_extraction_details(content_type, content_id, extracted_content)

            # Process content into chunks
            logger.info(f"Chunking content for {content_type} {content_id}")
            if content_type == "book":
                chunks = await _process_book_content(extracted_content, content_id, session, metadata)
            elif content_type == "video":
                chunks = await _process_video_content(extracted_content, content_id, session, metadata)
            else:
                msg = f"Unsupported content type: {content_type}"
                raise ValueError(msg)

            logger.info(f"Created {len(chunks)} chunks for {content_type} {content_id}")

            # Store embeddings
            logger.info(f"Storing embeddings for {content_type} {content_id}")
            vector_store = VectorStore()
            await _store_content_embeddings(session, content_type, content_id, chunks, metadata, vector_store)

        # Update status to completed (outside session to avoid conflicts)
        await _update_content_status(content_id, content_type, model_class, "completed")
        logger.info(f"✅ Successfully processed {content_type} {content_id} for RAG with {len(chunks)} chunks")

    except Exception as e:
        error_msg = f"Failed to process {content_type} {content_id} for RAG"
        logger.exception(f"❌ {error_msg}: {type(e).__name__}: {e!s}")

        # Update status to failed
        await _update_content_status(content_id, content_type, model_class, "failed", f"{type(e).__name__}: {e!s}")


async def _process_book_content(
    text_content: str, book_id: UUID, _session: AsyncSession, _metadata: dict[str, Any]
) -> list[str]:
    """Process book content into chunks."""
    # Chunk the text with chapter-aware chunking
    chunker = ChunkerFactory.create_chunker("book")
    chunks = chunker.chunk_text(text_content)
    logger.info(f"Book {book_id} chunked into {len(chunks)} pieces")
    return chunks


async def _process_video_content(
    content: list[dict] | str, video_uuid: UUID, session: AsyncSession, metadata: dict[str, Any]
) -> list[dict]:
    """Process video content into chunks."""
    # Check if we have transcript segments with timestamps
    if isinstance(content, list) and content:
        # Use timestamp-aware chunking with settings
        from src.config.settings import get_settings

        settings = get_settings()

        video_chunker = VideoTranscriptChunker(
            max_tokens=settings.RAG_VIDEO_MAX_TOKENS,
            overlap_tokens=settings.RAG_VIDEO_OVERLAP_TOKENS,
            target_duration_seconds=settings.RAG_VIDEO_TARGET_DURATION,
        )

        # Check if video has chapters
        chapters_result = await session.execute(
            select(VideoChapter).where(VideoChapter.video_id == video_uuid).order_by(VideoChapter.chapter_number)
        )
        chapters = chapters_result.scalars().all()

        # Choose chunking strategy
        if chapters and len(chapters) > 1:
            # Convert chapters to dict format
            chapter_dicts = [
                {"start_time": ch.start_time, "end_time": ch.end_time, "title": ch.title} for ch in chapters
            ]

            # Get video duration
            video_result = await session.execute(select(Video).where(Video.id == video_uuid))
            video = video_result.scalar_one_or_none()
            if not video:
                msg = f"Video {video_uuid} not found"
                raise ValueError(msg)

            video_chunks = video_chunker.chunk_by_chapters(content, chapter_dicts, str(video_uuid))
        else:
            # Use time-based chunking
            video_result = await session.execute(select(Video).where(Video.id == video_uuid))
            video = video_result.scalar_one_or_none()
            if not video:
                msg = f"Video {video_uuid} not found"
                raise ValueError(msg)

            video_chunks = video_chunker.chunk_transcript(content, video.duration, str(video_uuid))

        # Convert to format expected by vector store
        chunks = []
        for vc in video_chunks:
            chunk_dict = {
                "text": vc.text,
                "metadata": {
                    **vc.metadata,
                    "start_time": vc.start_time,
                    "end_time": vc.end_time,
                    "chunk_index": vc.chunk_index,
                    "total_chunks": vc.total_chunks,
                },
            }
            chunks.append(chunk_dict)

        logger.info(f"Created {len(chunks)} timestamp-aware chunks for video {video_uuid}")
        return chunks

    # Fallback to plain text chunking
    if not content:
        logger.warning(f"No transcript found for video {video_uuid}, skipping RAG processing")
        return []

    # Use default chunker for plain text
    chunker = ChunkerFactory.get_default_chunker()
    text_chunks = chunker.chunk_text(content)
    logger.info(f"Using fallback chunking for video {video_uuid} with {len(text_chunks)} chunks")

    # Convert to expected format
    return [{"text": chunk, "metadata": metadata} for chunk in text_chunks]


# Convenience functions for specific content types
async def process_book_rag_background(book_id: UUID) -> None:
    """Process book embedding for RAG in background."""
    extractor = BookContentExtractor()
    await process_content_rag_background(book_id, "book", extractor, Book)


async def process_video_rag_background(video_uuid: UUID) -> None:
    """Process video transcript for RAG in background."""
    extractor = VideoContentExtractor()
    await process_content_rag_background(video_uuid, "video", extractor, Video)
