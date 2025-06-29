"""Chunk storage service with batch processing for enhanced RAG system."""

import asyncio
import json
import logging
import traceback
from typing import Any
from uuid import UUID

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.session import async_session_maker

from .chunker import ChunkerFactory, DocumentChunk
from .vector_store import EmbeddingGenerator


logger = logging.getLogger(__name__)


class ChunkStorageService:
    """Service for storing document chunks with embeddings and batch processing."""

    def __init__(self) -> None:
        self.embedding_generator = EmbeddingGenerator()

    async def get_document_metadata(self, doc_id: UUID, doc_type: str) -> dict[str, Any]:
        """Get document metadata (title, author, etc.) based on type and ID."""
        metadata = {}

        async with async_session_maker() as session:
            try:
                query_map = {
                    "book": (
                        "SELECT title, author, subtitle, description FROM books WHERE id = :doc_id",
                        ["title", "author", "subtitle", "description"]
                    ),
                    "video": (
                        "SELECT title, description, channel_name FROM videos WHERE id = :doc_id",
                        ["title", "description", "channel:channel_name"]
                    ),
                    "course": (
                        "SELECT title, description FROM courses WHERE id = :doc_id",
                        ["title", "description"]
                    )
                }

                if doc_type in query_map:
                    query, fields = query_map[doc_type]
                    result = await session.execute(text(query), {"doc_id": str(doc_id)})
                    row = result.fetchone()

                    if row:
                        for field in fields:
                            if ":" in field:
                                # Handle renamed fields like "channel:channel_name"
                                key, attr = field.split(":")
                                metadata[key] = getattr(row, attr)
                            else:
                                metadata[key] = getattr(row, field)

            except Exception as e:
                logger.exception(f"Failed to get metadata for document {doc_id}: {e}")

        return metadata

    async def store_document_chunks(
        self, doc_id: UUID, doc_type: str, chunks: list[DocumentChunk], batch_size: int = 50
    ) -> None:
        """Store document chunks with embeddings in batches."""
        try:
            # Get document metadata once
            doc_metadata = await self._get_document_metadata(doc_id, doc_type)

            # Process chunks in batches to avoid memory issues
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i : i + batch_size]
                await self._store_chunk_batch(doc_id, doc_type, batch, doc_metadata)

            logger.info(f"Stored {len(chunks)} chunks for document {doc_id}")

        except Exception as e:
            logger.exception(f"Failed to store chunks for document {doc_id}: {e}")
            raise

    async def _store_chunk_batch(
        self, doc_id: UUID, doc_type: str, chunks: list[DocumentChunk], doc_metadata: dict[str, Any] | None = None
    ) -> None:
        """Store a batch of chunks with embeddings."""
        async with async_session_maker() as session:
            try:
                # Generate embeddings for all chunks in batch
                texts = [chunk.content for chunk in chunks]
                embeddings = await self.embedding_generator.generate_embeddings(texts)

                # Prepare batch insert data
                chunk_data = []
                for chunk, embedding in zip(chunks, embeddings, strict=False):
                    # Convert embedding list to PostgreSQL vector format
                    embedding_str = f"[{','.join(map(str, embedding))}]"

                    # Merge document metadata with chunk metadata
                    merged_metadata = chunk.metadata.copy() if chunk.metadata else {}
                    if doc_metadata:
                        merged_metadata.update(doc_metadata)

                    # Convert metadata dict to JSON string
                    metadata_json = json.dumps(merged_metadata)

                    chunk_data.append(
                        {
                            "doc_id": str(doc_id),
                            "doc_type": doc_type,
                            "chunk_index": chunk.chunk_index,
                            "content": chunk.content,
                            "embedding": embedding_str,
                            "metadata": metadata_json,
                        }
                    )

                # Batch insert using raw SQL for efficiency
                logger.info(f"Attempting to insert {len(chunk_data)} chunks")
                await self._batch_insert_chunks(session, chunk_data)
                logger.info("Batch insert completed, committing transaction")
                await session.commit()
                logger.info("Transaction committed successfully")

                logger.debug(f"Stored batch of {len(chunks)} chunks for document {doc_id}")

            except Exception as e:
                logger.exception(f"Failed to store chunk batch for document {doc_id}: {e}")
                logger.exception(f"Error type: {type(e)}")
                traceback.print_exc()
                await session.rollback()
                raise

    async def _batch_insert_chunks(self, session: AsyncSession, chunk_data: list[dict[str, Any]]) -> None:
        """Perform batch insert of chunks using efficient SQL."""
        if not chunk_data:
            return

        # Use PostgreSQL's COPY or bulk insert for efficiency
        insert_query = text("""
            INSERT INTO rag_document_chunks (doc_id, doc_type, chunk_index, content, embedding, metadata, created_at)
            VALUES (:doc_id, :doc_type, :chunk_index, :content, :embedding, :metadata, NOW())
            ON CONFLICT (doc_id, chunk_index) DO UPDATE SET
                content = EXCLUDED.content,
                embedding = EXCLUDED.embedding,
                metadata = EXCLUDED.metadata,
                created_at = NOW()
        """)

        # Convert numpy arrays to lists for JSON serialization
        for data in chunk_data:
            if isinstance(data["embedding"], np.ndarray):
                data["embedding"] = data["embedding"].tolist()

        # Execute batch insert using executemany for multiple parameter sets
        for data in chunk_data:
            await session.execute(insert_query, data)

    async def delete_document_chunks(self, doc_id: UUID) -> int:
        """Delete all chunks for a document."""
        async with async_session_maker() as session:
            try:
                result = await session.execute(
                    text("DELETE FROM rag_document_chunks WHERE doc_id = :doc_id"), {"doc_id": str(doc_id)}
                )
                deleted_count = result.rowcount
                await session.commit()

                logger.info(f"Deleted {deleted_count} chunks for document {doc_id}")
                return deleted_count

            except Exception as e:
                await session.rollback()
                logger.exception(f"Failed to delete chunks for document {doc_id}: {e}")
                raise

    async def get_document_chunk_count(self, doc_id: UUID) -> int:
        """Get the number of chunks for a document."""
        async with async_session_maker() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM rag_document_chunks WHERE doc_id = :doc_id"), {"doc_id": str(doc_id)}
            )
            return result.scalar() or 0


class BatchProcessingService:
    """Service for managing batch processing of documents for chunking."""

    def __init__(self) -> None:
        self.chunk_storage = ChunkStorageService()

    async def queue_document_for_processing(
        self, doc_id: UUID, doc_type: str, priority: int = 5, metadata: dict[str, Any] | None = None
    ) -> None:
        """Add document to processing queue."""
        async with async_session_maker() as session:
            try:
                await session.execute(
                    text("""
                        INSERT INTO chunk_processing_queue (doc_id, doc_type, priority, metadata)
                        VALUES (:doc_id, :doc_type, :priority, :metadata)
                        ON CONFLICT (doc_id, doc_type) DO UPDATE SET
                            priority = EXCLUDED.priority,
                            metadata = EXCLUDED.metadata,
                            status = 'pending',
                            error_message = NULL,
                            created_at = NOW()
                    """),
                    {
                        "doc_id": str(doc_id),
                        "doc_type": doc_type,
                        "priority": priority,
                        "metadata": json.dumps(metadata or {}),
                    },
                )
                await session.commit()
                logger.info(f"Queued document {doc_id} for processing")

            except Exception as e:
                await session.rollback()
                logger.exception(f"Failed to queue document {doc_id}: {e}")
                raise

    async def process_next_document(self) -> dict[str, Any] | None:
        """Process the next document in the queue."""
        async with async_session_maker() as session:
            try:
                # Get the next document to process
                result = await session.execute(
                    text("""
                        UPDATE chunk_processing_queue
                        SET status = 'processing', started_at = NOW()
                        WHERE id = (
                            SELECT id FROM chunk_processing_queue
                            WHERE status = 'pending'
                            ORDER BY priority DESC, created_at ASC
                            LIMIT 1
                            FOR UPDATE SKIP LOCKED
                        )
                        RETURNING doc_id, doc_type, metadata
                    """)
                )

                row = result.fetchone()
                if not row:
                    return None  # No documents to process

                await session.commit()

                doc_id = UUID(row.doc_id)
                doc_type = row.doc_type
                metadata = row.metadata or {}

                logger.info(f"Processing document {doc_id} of type {doc_type}")

                # Process the document
                await self._process_document(doc_id, doc_type, metadata)

                # Mark as completed
                await self._mark_processing_completed(doc_id, doc_type)

                return {"doc_id": doc_id, "doc_type": doc_type, "status": "completed"}

            except Exception as e:
                # Mark as failed
                await self._mark_processing_failed(doc_id, doc_type, str(e))
                logger.exception(f"Failed to process document {doc_id}: {e}")
                raise

    async def _process_document(self, doc_id: UUID, doc_type: str, metadata: dict[str, Any]) -> None:
        """Process a single document by chunking and storing."""
        try:
            # Get document content based on type
            content = await self._get_document_content(doc_id, doc_type, metadata)

            if not content:
                msg = f"No content found for document {doc_id}"
                raise ValueError(msg)

            # Get document metadata for chunker
            chunk_storage = ChunkStorageService()
            doc_metadata = await chunk_storage.get_document_metadata(doc_id, doc_type)

            # Create appropriate chunker with metadata
            chunker = ChunkerFactory.create_chunker(doc_type, metadata=doc_metadata)

            # Chunk the document
            chunks = chunker.chunk_document(doc_id, doc_type, content)

            if not chunks:
                logger.warning(f"No chunks generated for document {doc_id}")
                return

            # Delete existing chunks
            await self.chunk_storage.delete_document_chunks(doc_id)

            # Store new chunks
            await self.chunk_storage.store_document_chunks(doc_id, doc_type, chunks)

            logger.info(f"Successfully processed document {doc_id} with {len(chunks)} chunks")

        except Exception as e:
            logger.exception(f"Error processing document {doc_id}: {e}")
            raise

    async def _get_document_content(self, doc_id: UUID, doc_type: str, metadata: dict[str, Any]) -> str | None:  # noqa: ARG002
        """Get document content based on type and ID."""
        async with async_session_maker() as session:
            try:
                if doc_type == "book":
                    # Get book file path
                    result = await session.execute(
                        text("SELECT file_path FROM books WHERE id = :doc_id"), {"doc_id": str(doc_id)}
                    )
                    row = result.fetchone()
                    return row.file_path if row else None

                if doc_type == "video":
                    # Get video content or transcript
                    result = await session.execute(
                        text("SELECT url, title, description FROM videos WHERE id = :doc_id"), {"doc_id": str(doc_id)}
                    )
                    row = result.fetchone()
                    if row:
                        # For now, return URL for transcript extraction
                        return row.url
                    return None

                if doc_type == "course":
                    # Get course lessons content
                    result = await session.execute(
                        text("""
                            SELECT string_agg(content, E'\n\n') as course_content
                            FROM lessons l
                            JOIN courses c ON l.course_id = c.id
                            WHERE c.id = :doc_id
                        """),
                        {"doc_id": str(doc_id)},
                    )
                    row = result.fetchone()
                    return row.course_content if row else None

                logger.error(f"Unknown document type: {doc_type}")
                return None

            except Exception as e:
                logger.exception(f"Failed to get content for document {doc_id}: {e}")
                return None

    async def _mark_processing_completed(self, doc_id: UUID, doc_type: str) -> None:
        """Mark document processing as completed."""
        async with async_session_maker() as session:
            await session.execute(
                text("""
                    UPDATE chunk_processing_queue
                    SET status = 'completed', completed_at = NOW()
                    WHERE doc_id = :doc_id AND doc_type = :doc_type
                """),
                {"doc_id": str(doc_id), "doc_type": doc_type},
            )
            await session.commit()

    async def _mark_processing_failed(self, doc_id: UUID, doc_type: str, error_message: str) -> None:
        """Mark document processing as failed."""
        async with async_session_maker() as session:
            await session.execute(
                text("""
                    UPDATE chunk_processing_queue
                    SET status = 'failed', error_message = :error_message, completed_at = NOW()
                    WHERE doc_id = :doc_id AND doc_type = :doc_type
                """),
                {"doc_id": str(doc_id), "doc_type": doc_type, "error_message": error_message},
            )
            await session.commit()

    async def get_processing_status(self, doc_id: UUID, doc_type: str) -> dict[str, Any] | None:
        """Get processing status for a document."""
        async with async_session_maker() as session:
            result = await session.execute(
                text("""
                    SELECT status, priority, error_message, created_at, started_at, completed_at
                    FROM chunk_processing_queue
                    WHERE doc_id = :doc_id AND doc_type = :doc_type
                """),
                {"doc_id": str(doc_id), "doc_type": doc_type},
            )

            row = result.fetchone()
            if not row:
                return None

            return {
                "status": row.status,
                "priority": row.priority,
                "error_message": row.error_message,
                "created_at": row.created_at,
                "started_at": row.started_at,
                "completed_at": row.completed_at,
            }

    async def process_pending_documents(self, max_documents: int = 10) -> list[dict[str, Any]]:
        """Process multiple pending documents."""
        results = []

        for _ in range(max_documents):
            result = await self.process_next_document()
            if not result:
                break  # No more documents to process
            results.append(result)

        return results


# Background task runner
async def run_batch_processor(max_concurrent: int = 3) -> None:
    """Run batch processor as background task."""
    processor = BatchProcessingService()

    while True:
        try:
            # Process documents concurrently
            tasks = []
            for _ in range(max_concurrent):
                task = asyncio.create_task(processor.process_next_document())
                tasks.append(task)

            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Check if any documents were processed
            processed_any = any(result and not isinstance(result, Exception) for result in results)

            if not processed_any:
                # No documents to process, wait before checking again
                await asyncio.sleep(10)

        except Exception as e:
            logger.exception(f"Error in batch processor: {e}")
            await asyncio.sleep(30)  # Wait longer on error
