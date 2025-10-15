"""RAG system service layer orchestrating LiteLLM + pgvector RAG flows."""

import contextlib
import logging
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from src.ai.rag.chunker import chunk_text_async
from src.ai.rag.config import rag_config
from src.ai.rag.parser import DocumentProcessor
from src.ai.rag.schemas import DocumentResponse, SearchResult
from src.auth import AuthContext
from src.books.models import Book
from src.courses.models import CourseDocument
from src.storage.factory import get_storage_provider
from src.videos.models import Video


logger = logging.getLogger(__name__)


class RAGService:
    """RAG service orchestrator built on LiteLLM embeddings and pgvector storage."""

    def __init__(self) -> None:
        """Initialize RAG service components for LiteLLM + pgvector pipeline."""
        # Configuration from centralized config
        self.config = rag_config

        # Components will be lazily initialized
        self._document_processor = None  # Unstructured parser

    @property
    def document_processor(self) -> DocumentProcessor:
        """Lazy load document processor."""
        if self._document_processor is None:
            self._document_processor = DocumentProcessor()
        return self._document_processor



    async def upload_document(
        self,
        auth: AuthContext,
        course_id: uuid.UUID,
        document_type: str,
        title: str,
        file_content: bytes | None = None,
        url: str | None = None,
        filename: str | None = None,
    ) -> DocumentResponse:
        """Upload a document to a course, ensuring user ownership."""
        # Validate user owns the course
        await auth.validate_resource("course", course_id)

        try:
            # Create document record
            doc = CourseDocument(
                course_id=course_id,
                title=title,
                source_url=url,
                document_type=document_type or "unknown",
                status="pending",  # Start as pending for processing
            )
            auth.session.add(doc)
            await auth.session.flush()

            # Store file if provided
            if file_content and filename:
                # Check file size limit
                file_size_mb = len(file_content) / (1024 * 1024)
                if file_size_mb > self.config.max_file_size_mb:
                    logger.warning(
                        "File %s too large: %.2fMB > %dMB limit",
                        filename, file_size_mb, self.config.max_file_size_mb
                    )
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large: {file_size_mb:.1f}MB exceeds {self.config.max_file_size_mb}MB limit"
                    )

                from src.config.settings import get_settings

                settings = get_settings()
                # NOTE: RAG documents are stored separately from main user files (books)
                # This is intentional - RAG documents are course-specific reference materials
                # while books are user-owned files with different access patterns
                rag_document_dir = Path(settings.LOCAL_STORAGE_PATH) / "rag_documents" / str(course_id)
                rag_document_dir.mkdir(parents=True, exist_ok=True)

                # Security fix: Use only UUID + validated extension, no user-provided filename in path
                # This prevents path traversal attacks while preserving file type handling
                ext = Path(filename).suffix.lower() if filename else ""
                allowed_extensions = {".pdf", ".txt", ".md", ".epub"}
                safe_ext = ext if ext in allowed_extensions else ""

                file_path = rag_document_dir / f"{doc.id}{safe_ext}"
                file_path.write_bytes(file_content)

                doc.file_path = str(file_path)

            await auth.session.commit()

            # Process the document immediately after upload
            doc_id = doc.id  # Capture ID before potential session issues
            try:
                await self.process_document(auth.session, doc_id)
            except Exception:
                logger.exception("Failed to process document %s", doc_id)
                # Don't fail the upload if processing fails - it can be retried later

            # Re-query to get a Row object that works with model_validate
            # This matches the pattern used in get_document() and get_documents()
            result = await auth.session.execute(
                text("SELECT * FROM course_documents WHERE id = :doc_id"),
                {"doc_id": doc.id}
            )
            row = result.fetchone()
            if row is None:
                msg = f"Course document {doc.id} not found after creation"
                raise HTTPException(status_code=404, detail=msg)

            return DocumentResponse.model_validate(dict(row._mapping))

        except Exception as e:
            await auth.session.rollback()
            logger.exception("Failed to upload document")
            raise HTTPException(status_code=500, detail=str(e)) from e

    async def process_document(self, session: AsyncSession, document_id: int) -> None:
        """Process a document (parse, chunk, embed, index)."""
        try:
            # Update status to processing
            await session.execute(
                text("UPDATE course_documents SET status = 'processing' WHERE id = :doc_id"),
                {"doc_id": document_id},
            )
            await session.commit()

            # Get document
            result = await session.execute(
                text("SELECT * FROM course_documents WHERE id = :doc_id"), {"doc_id": document_id}
            )
            doc_row = result.fetchone()
            if not doc_row:
                msg = f"Document {document_id} not found"
                raise ValueError(msg)

            doc_dict = dict(doc_row._mapping)

            # Extract text using Unstructured parser
            text_content = ""
            if doc_dict["document_type"] == "url" and doc_dict["source_url"]:
                # TODO: Parse URL with Unstructured
                text_content, crawl_date = await self.document_processor.process_url_document(doc_dict["source_url"])
                await session.execute(
                    text("UPDATE course_documents SET crawl_date = :crawl_date WHERE id = :doc_id"),
                    {"crawl_date": crawl_date, "doc_id": document_id},
                )
            elif doc_dict["file_path"]:
                # Process file using temp copy for efficient memory usage
                stored_file_path = Path(doc_dict["file_path"])
                if not stored_file_path.exists():
                    msg = f"Stored file not found: {stored_file_path}"
                    raise ValueError(msg)

                # Create temp file and copy content
                with tempfile.NamedTemporaryFile(delete=False, suffix=stored_file_path.suffix) as temp_file:
                    temp_file.write(stored_file_path.read_bytes())
                    temp_file_path = temp_file.name

                try:
                    # Process the temp file
                    text_content = await self.document_processor.process_document(
                        temp_file_path, doc_dict["document_type"]
                    )
                finally:
                    # Always clean up temp file
                    with contextlib.suppress(OSError):
                        Path(temp_file_path).unlink()
            else:
                msg = "No file path or URL to process"
                raise ValueError(msg)

            # Chunk text using Chonkie
            chunks = await chunk_text_async(text_content)
            logger.info("Document %s chunked into %s pieces", document_id, len(chunks))

            # Store chunks in pgvector via VectorRAG helper
            await self._store_document_chunks(session, document_id, chunks)

            # Update status to embedded
            await session.execute(
                text("""
                    UPDATE course_documents
                    SET status = 'embedded',
                        processed_at = NOW(),
                        embedded_at = NOW()
                    WHERE id = :doc_id
                """),
                {"doc_id": document_id},
            )
            await session.commit()

            logger.info("Successfully processed document %s", document_id)

            # Clean up stored source file after successful processing
            # Course documents are reference materials, not user-viewed content like books
            if doc_dict.get("file_path"):
                try:
                    file_path = Path(doc_dict["file_path"])
                    if file_path.exists():
                        file_path.unlink()
                        logger.debug("Cleaned up source file for document %s", document_id)
                except Exception:
                    # Do not fail the request if cleanup fails
                    logger.debug("Post-process source cleanup failed for document %s", document_id)

        except Exception:
            logger.exception("Failed to process document %s", document_id)
            await session.execute(
                text("UPDATE course_documents SET status = 'failed' WHERE id = :doc_id"), {"doc_id": document_id}
            )
            await session.commit()
            raise

    async def _cleanup_course_source_file(self, session: AsyncSession, document_id: int, file_path_str: str | None) -> None:
        """Delete a local course document source file and clear file_path in DB."""
        if not file_path_str:
            return
        fp = Path(file_path_str)
        if fp.exists():
            with contextlib.suppress(Exception):
                fp.unlink()
        await session.execute(
            text("UPDATE course_documents SET file_path = NULL WHERE id = :doc_id"),
            {"doc_id": document_id},
        )
        await session.commit()

    async def _cleanup_book_source_file(self, session: AsyncSession, book_id: uuid.UUID) -> None:
        """Delete a stored book file via storage provider and clear file_path in DB."""
        # Reload latest book row to ensure we have current file_path
        book = await session.get(Book, book_id)
        if not book or not getattr(book, "file_path", None):
            return
        storage = get_storage_provider()
        with contextlib.suppress(Exception):
            await storage.delete(book.file_path)  # type: ignore[arg-type]
        # Clear DB reference
        book.file_path = None  # type: ignore[assignment]
        await session.commit()

    async def process_book(self, session: AsyncSession, book_id: uuid.UUID) -> None:
        """Process a book (parse, chunk, embed, index) with unified RAG pipeline."""
        try:
            # Load book
            book = await session.get(Book, book_id)
            if not book:
                logger.warning("Book %s not found for processing", book_id)
                return

            # Validate file
            if not getattr(book, "file_path", None):
                logger.warning("Book %s has no file path; marking as failed", book_id)
                book.rag_status = "failed"
                with contextlib.suppress(Exception):  # type: ignore[name-defined]
                    book.rag_error = "missing_file"  # type: ignore[attr-defined]
                await session.commit()
                return

            # Mark processing
            book.rag_status = "processing"
            await session.commit()

            # Download file
            storage = get_storage_provider()
            file_bytes = await storage.download(book.file_path)

            # Parse via Unstructured using a secure temp file
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=f".{(book.file_type or 'pdf').lower()}"
            ) as temp_file:
                temp_file.write(file_bytes)
                temp_path = temp_file.name
            try:
                text_content = await self.document_processor.process_document(
                    temp_path, (book.file_type or "pdf").lower()
                )
            finally:
                # Always clean up temp file
                with contextlib.suppress(OSError):
                    Path(temp_path).unlink()

            # Chunk
            chunks = await chunk_text_async(text_content)

            # Store chunks
            if not hasattr(self, "_vector_rag"):
                from src.ai.rag.embeddings import VectorRAG
                self._vector_rag = VectorRAG()

            await self._vector_rag.store_document_chunks_with_embeddings(
                session=session,
                doc_type="book",
                doc_id=book.id,
                title=book.title or "",
                chunks=chunks,
            )

            # Mark completed
            book.rag_status = "completed"
            book.rag_processed_at = datetime.now(UTC)
            await session.commit()

            logger.info("Successfully processed book %s", book_id)

            # Note: We do not delete the original book file here; keep for user access

        except StaleDataError:
            # Book row was deleted between load and commit; treat as benign and exit quietly
            with contextlib.suppress(Exception):
                await session.rollback()
            logger.info("Book %s was deleted during processing; aborting embedding", book_id)
            return
        except Exception:
            logger.exception("Failed to process book %s", book_id)
            # Best-effort mark failed
            try:
                book = await session.get(Book, book_id)
                if book:
                    book.rag_status = "failed"
                    await session.commit()
            except Exception:
                await session.rollback()
            raise

    async def process_video(self, session: AsyncSession, video_id: uuid.UUID) -> None:
        """Process a video (transcript segments to chunks → embed → index)."""
        try:
            video = await session.get(Video, video_id)
            if not video:
                logger.warning("Video %s not found for processing", video_id)
                return

            # Mark processing
            video.rag_status = "processing"
            await session.commit()

            # Collect transcript chunks
            chunks, per_chunk_meta = await self._collect_video_transcript_chunks(video)

            if not chunks:
                video.rag_status = "failed"
                await session.commit()
                return

            # Store chunks (current API: per-chunk to preserve per-chunk metadata)
            if not hasattr(self, "_vector_rag"):
                from src.ai.rag.embeddings import VectorRAG

                self._vector_rag = VectorRAG()

            for idx, chunk in enumerate(chunks):
                meta = per_chunk_meta[idx] if idx < len(per_chunk_meta) else {}
                await self._vector_rag.store_document_chunks_with_embeddings(
                    session=session,
                    doc_type="video",
                    doc_id=video.id,
                    title=video.title or "",
                    chunks=[chunk],
                    extra_metadata=meta,
                )

            # Mark completed
            video.rag_status = "completed"
            video.rag_processed_at = datetime.now(UTC)
            await session.commit()

            logger.info("Successfully processed video %s", video_id)

        except Exception:
            logger.exception("Failed to process video %s", video_id)
            try:
                video = await session.get(Video, video_id)
                if video:
                    video.rag_status = "failed"
                    await session.commit()
            except Exception:
                await session.rollback()
            raise

    async def _collect_video_transcript_chunks(self, video: Video) -> tuple[list[str], list[dict]]:
        """Collect transcript chunks and per-chunk metadata for a video.

        Prefer structured segments with timestamps from transcript_data; otherwise
        fall back to chunking the raw transcript text via the default chunker.
        """
        chunks: list[str] = []
        per_chunk_meta: list[dict] = []

        segments = None
        if getattr(video, "transcript_data", None) and isinstance(video.transcript_data, dict):
            segments = video.transcript_data.get("segments")

        if segments:
            for seg in segments:
                text_val = (seg.get("text") or "").strip()
                if not text_val:
                    continue
                chunks.append(text_val)
                per_chunk_meta.append({"start": seg.get("start"), "end": seg.get("end")})
        else:
            transcript = getattr(video, "transcript", None)
            if isinstance(transcript, str) and transcript:
                chunks = await chunk_text_async(transcript)
                per_chunk_meta = [{} for _ in chunks]

        return chunks, per_chunk_meta

    async def _store_document_chunks(self, session: AsyncSession, document_id: int, chunks: list[str]) -> None:
        """Store document chunks with embeddings using VectorRAG."""
        try:
            # Get document metadata
            result = await session.execute(
                text("""
                    SELECT id, course_id as course_id, title, document_type
                    FROM course_documents
                    WHERE id = :doc_id
                """),
                {"doc_id": document_id},
            )
            doc_info = result.fetchone()

            if not doc_info:
                msg = f"Document {document_id} not found"
                raise ValueError(msg)

            # Determine deterministic UUID for course document
            doc_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, f"document_{document_id}")

            # Prepare chunks to ensure we don't call VectorRAG with empty content
            valid_chunk_count = sum(1 for chunk in chunks if chunk.strip())
            if not valid_chunk_count:
                logger.warning("No valid chunks to index for document %s", document_id)
                return

            logger.info("Storing %s chunks for document %s using LiteLLM + pgvector", valid_chunk_count, document_id)

            # Get VectorRAG instance
            if not hasattr(self, "_vector_rag"):
                from src.ai.rag.embeddings import VectorRAG

                self._vector_rag = VectorRAG()

            # Use VectorRAG's existing method to store chunks with embeddings
            await self._vector_rag.store_document_chunks_with_embeddings(
                session=session,
                doc_type="course",
                doc_id=doc_uuid,
                title=doc_info.title,
                chunks=chunks,
                course_id=doc_info.course_id,
                extra_metadata={
                    "document_id": document_id,
                },
            )

            logger.info("Successfully stored %s chunks for document %s in pgvector", len(chunks), document_id)

        except Exception:
            logger.exception("Failed to store document chunks")
            raise

    async def search_documents(
        self, auth: AuthContext, course_id: uuid.UUID, query: str, top_k: int | None = None
    ) -> list[SearchResult]:
        """Search documents using AuthContext, ensuring user ownership."""
        await auth.validate_resource("course", course_id)
        return await self.search_course_documents(auth.session, course_id, query, top_k)

    async def search_course_documents(
        self, session: AsyncSession, course_id: uuid.UUID, query: str, top_k: int | None = None
    ) -> list[SearchResult]:
        """Search course documents via unified VectorRAG.search with course_id filter."""
        try:
            if top_k is None:
                top_k = self.config.rerank_k

            # Lazy init
            if not hasattr(self, "_vector_rag"):
                from src.ai.rag.embeddings import VectorRAG

                self._vector_rag = VectorRAG()

            return await self._vector_rag.search(
                session=session,
                doc_type="course",
                query=query,
                limit=top_k,
                course_id=course_id,
            )

        except Exception:
            logger.exception("Failed to search documents")
            return []

    async def get_documents(
        self, auth: AuthContext, course_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> list[DocumentResponse]:
        """Get documents for a course, ensuring user ownership."""
        # Verify user owns the course - this will throw 404 if not found or not owned
        await auth.validate_resource("course", course_id)

        try:
            # Now we know the user owns the course, we can query its documents directly
            # No need to join with courses again since ownership is already verified
            result = await auth.session.execute(
                text("""
                    SELECT * FROM course_documents
                    WHERE course_id = :course_id
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :skip
                """),
                {"course_id": str(course_id), "limit": limit, "skip": skip},
            )

            return [DocumentResponse.model_validate(dict(row._mapping)) for row in result.fetchall()]
        except Exception:
            logger.exception("Failed to get documents")
            # Return empty list instead of crashing
            return []

    async def count_documents(self, auth: AuthContext, course_id: uuid.UUID) -> int:
        """Count documents for a course, ensuring user ownership."""
        # Verify user owns the course - this will throw 404 if not found or not owned
        await auth.validate_resource("course", course_id)

        try:
            # Now we know the user owns the course, we can count its documents directly
            result = await auth.session.execute(
                text("""
                    SELECT COUNT(*) FROM course_documents
                    WHERE course_id = :course_id
                """),
                {"course_id": str(course_id)},
            )
            return result.scalar_one_or_none() or 0
        except Exception:
            logger.exception("Failed to count documents")
            return 0

    async def delete_document(self, auth: AuthContext, document_id: int) -> None:
        """Delete a document and its chunks, ensuring user ownership."""
        try:
            # First get the document to find its course_id
            result = await auth.session.execute(
                text("""
                    SELECT id, file_path, course_id
                    FROM course_documents
                    WHERE id = :doc_id
                """),
                {"doc_id": document_id},
            )
            doc = result.fetchone()

            if not doc:
                raise HTTPException(status_code=404, detail="Document not found")

            # Verify user owns the course that contains this document
            await auth.validate_resource("course", doc.course_id)

            # Delete file from filesystem if it exists
            if doc.file_path:
                try:
                    file_path = Path(doc.file_path)
                    if file_path.exists():
                        file_path.unlink()
                except Exception as e:
                    logger.warning("Failed to delete file %s: %s", doc.file_path, e)

            # Old document_chunks table has been removed - chunks are now in rag_document_chunks
            # Delete from rag_document_chunks using the doc_uuid scheme
            doc_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, f"document_{document_id}")
            chunks_result = await auth.session.execute(
                text("DELETE FROM rag_document_chunks WHERE doc_id = :doc_uuid AND doc_type = 'course'"),
                {"doc_uuid": str(doc_uuid)},
            )
            chunks_deleted = int(getattr(chunks_result, "rowcount", 0) or 0)
            if chunks_deleted > 0:
                logger.info(f"Deleted {chunks_deleted} RAG chunks for document {document_id}")

            # Delete document
            await auth.session.execute(text("DELETE FROM course_documents WHERE id = :doc_id"), {"doc_id": document_id})

            await auth.session.commit()
            logger.info("Successfully deleted document %s", document_id)

        except Exception:
            await auth.session.rollback()
            logger.exception("Failed to delete document %s", document_id)
            raise

    async def get_document(self, auth: AuthContext, document_id: int) -> DocumentResponse:
        """Get a single document, ensuring user ownership."""
        try:
            # First get the document
            result = await auth.session.execute(
                text("""
                    SELECT * FROM course_documents
                    WHERE id = :doc_id
                """),
                {"doc_id": document_id},
            )
            row = result.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Document not found")

            # Verify user owns the course that contains this document
            await auth.validate_resource("course", row.course_id)

            return DocumentResponse.model_validate(dict(row._mapping))
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Error getting document %s", document_id)
            raise HTTPException(status_code=500, detail="Failed to get document") from e

    @staticmethod
    async def delete_chunks_by_doc_id(
        session: AsyncSession,
        document_id: str,
        doc_type: str = "course",
    ) -> int:
        """
        Delete all RAG chunks for a specific document.

        For courses: Uses uuid5(NAMESPACE_DNS, f"document_{document_id}")
        For books: Uses the book_id directly as doc_id when RAG storage is enabled

        Returns the number of chunks deleted.
        """
        import time

        start_time = time.time()

        try:
            if doc_type == "book":
                # For books, doc_id is the book_id directly
                result = await session.execute(
                    text("DELETE FROM rag_document_chunks WHERE doc_id = :doc_id AND doc_type = :doc_type"),
                    {"doc_id": document_id, "doc_type": doc_type},
                )
            else:
                # For courses, compute the UUID
                doc_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, f"document_{document_id}")
                result = await session.execute(
                    text("DELETE FROM rag_document_chunks WHERE doc_id = :doc_uuid AND doc_type = :doc_type"),
                    {"doc_uuid": str(doc_uuid), "doc_type": doc_type},
                )

            await session.commit()
            rowcount = int(getattr(result, "rowcount", 0) or 0)

            elapsed_time = time.time() - start_time
            logger.info(
                "Deleted %s RAG chunks for %s document %s in %.2f seconds",
                rowcount,
                doc_type,
                document_id,
                elapsed_time,
            )

            return rowcount

        except Exception:
            logger.exception("Error deleting RAG chunks for document %s", document_id)
            await session.rollback()
            # Don't raise - this is best-effort cleanup
            return 0

    @staticmethod
    async def delete_chunks_by_course_id(
        session: AsyncSession,
        course_id: str,
    ) -> int:
        """
        Delete all RAG chunks for a specific course using metadata.

        Deletes from rag_document_chunks WHERE metadata->>'course_id' = :course_id

        Returns the number of chunks deleted.
        """
        import time

        start_time = time.time()

        try:
            result = await session.execute(
                text(
                    "DELETE FROM rag_document_chunks WHERE metadata->>'course_id' = :course_id AND doc_type = 'course'"
                ),
                {"course_id": course_id},
            )

            await session.commit()
            rowcount = int(getattr(result, "rowcount", 0) or 0)

            elapsed_time = time.time() - start_time
            logger.info(
                "Deleted %s RAG chunks for course %s in %.2f seconds",
                rowcount,
                course_id,
                elapsed_time,
            )

            return rowcount

        except Exception:
            logger.exception("Error deleting RAG chunks for course %s", course_id)
            await session.rollback()
            # Don't raise - this is best-effort cleanup
            return 0
