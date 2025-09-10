"""RAG system service layer using txtai."""

import logging
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from txtai.embeddings import Embeddings

from src.ai.rag.chunker import ChunkerFactory
from src.ai.rag.config import rag_config
from src.ai.rag.parser import DocumentProcessor
from src.ai.rag.schemas import DocumentResponse, SearchResult
from src.courses.models import CourseDocument


logger = logging.getLogger(__name__)


class RAGService:
    """RAG service orchestrator using txtai and related libraries."""

    # Singleton instance
    _instance: Optional["RAGService"] = None
    _initialized = False

    def __new__(cls) -> "RAGService":
        """Singleton pattern to prevent multiple initializations."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize RAG service with txtai components."""
        if not self._initialized:
            # Configuration from centralized config
            self.config = rag_config

            # Components will be lazily initialized
            self._embeddings = None  # txtai Embeddings
            self._document_processor = None  # Unstructured parser
            self._chunker = None  # Chonkie chunker

            self._initialized = True

    @property
    def embeddings(self) -> Embeddings:
        """Get txtai embeddings - but we're not using it anymore.

        We use VectorRAG directly for embeddings since it already handles:
        - LiteLLM embeddings generation
        - pgvector storage
        - Search functionality

        This property is kept for backward compatibility but delegates to VectorRAG.
        """
        if self._embeddings is None:
            # We don't really need txtai for embeddings anymore
            # VectorRAG handles everything
            logger.info("Note: Using VectorRAG for embeddings, not txtai")

            # Create a minimal txtai instance if needed for compatibility
            # But the actual work is done by VectorRAG
            self._embeddings = Embeddings(
                {
                    "content": True,  # In-memory only
                    "backend": "numpy",  # Simple backend
                }
            )

        return self._embeddings

    @property
    def document_processor(self) -> DocumentProcessor:
        """Lazy load document processor."""
        if self._document_processor is None:
            self._document_processor = DocumentProcessor()
        return self._document_processor

    @property
    def chunker(self) -> Any:
        """Lazy load Chonkie chunker."""
        if self._chunker is None:
            self._chunker = ChunkerFactory.get_default_chunker()
        return self._chunker

    async def upload_document(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        document_type: str,
        title: str,
        file_content: bytes | None = None,
        url: str | None = None,
        filename: str | None = None,
    ) -> DocumentResponse:
        """Upload a document to a course."""
        # Validate user owns the course
        await self.validate_course_ownership(session, course_id, user_id)

        try:
            # Create document record
            doc = CourseDocument(
                course_id=course_id,
                title=title,
                source_url=url,
                document_type=document_type or "unknown",
                status="pending",  # Start as pending for processing
            )
            session.add(doc)
            await session.flush()

            # Store file if provided
            if file_content and filename:
                from src.config.settings import get_settings

                settings = get_settings()
                upload_dir = Path(settings.LOCAL_STORAGE_PATH) / "documents" / str(course_id)
                upload_dir.mkdir(parents=True, exist_ok=True)

                file_path = upload_dir / f"{doc.id}_{filename}"
                file_path.write_bytes(file_content)

                doc.file_path = str(file_path)  # type: ignore[assignment]

            await session.commit()

            # Process the document immediately after upload
            try:
                await self.process_document(session, doc.id)
            except Exception:
                logger.exception("Failed to process document %s", doc.id)
                # Don't fail the upload if processing fails - it can be retried later

            return DocumentResponse(
                id=doc.id,
                course_id=doc.course_id,
                document_type=doc.document_type or "unknown",
                title=doc.title,
                file_path=doc.file_path,
                url=doc.url,
                source_url=doc.source_url,
                crawl_date=doc.crawl_date,
                content_hash=doc.content_hash,
                doc_metadata=doc.doc_metadata,
                created_at=doc.created_at,
                processed_at=doc.processed_at,
                embedded_at=doc.embedded_at,
                status=doc.status,
            )

        except Exception as e:
            await session.rollback()
            logger.exception("Failed to upload document")
            raise HTTPException(status_code=500, detail=str(e)) from e

    async def process_document(self, session: AsyncSession, document_id: int) -> None:
        """Process a document (parse, chunk, embed, index)."""
        try:
            # Update status to processing
            await session.execute(
                text("UPDATE roadmap_documents SET status = 'processing' WHERE id = :doc_id"),
                {"doc_id": document_id},
            )
            await session.commit()

            # Get document
            result = await session.execute(
                text("SELECT * FROM roadmap_documents WHERE id = :doc_id"), {"doc_id": document_id}
            )
            doc_row = result.fetchone()
            if not doc_row:
                msg = f"Document {document_id} not found"
                raise ValueError(msg)

            doc_dict = doc_row._asdict()

            # Extract text using Unstructured parser
            text_content = ""
            if doc_dict["document_type"] == "url" and doc_dict["source_url"]:
                # TODO: Parse URL with Unstructured
                text_content, crawl_date = await self.document_processor.process_url_document(doc_dict["source_url"])
                await session.execute(
                    text("UPDATE roadmap_documents SET crawl_date = :crawl_date WHERE id = :doc_id"),
                    {"crawl_date": crawl_date, "doc_id": document_id},
                )
            elif doc_dict["file_path"]:
                # TODO: Parse file with Unstructured for better extraction
                # Should handle tables, OCR, complex layouts
                text_content = await self.document_processor.process_document(
                    doc_dict["file_path"], doc_dict["document_type"]
                )
            else:
                msg = "No file path or URL to process"
                raise ValueError(msg)

            # Chunk via centralized chunker
            chunks = await self.chunker.chunk_text_async(text_content)
            logger.info("Document %s chunked into %s pieces", document_id, len(chunks))

            # Store chunks in txtai/pgvector
            # TODO: Use txtai's index method instead of custom storage
            await self._store_document_chunks(session, document_id, chunks)

            # Update status to embedded
            await session.execute(
                text("""
                    UPDATE roadmap_documents
                    SET status = 'embedded',
                        processed_at = NOW(),
                        embedded_at = NOW()
                    WHERE id = :doc_id
                """),
                {"doc_id": document_id},
            )
            await session.commit()

            logger.info("Successfully processed document %s", document_id)

        except Exception:
            logger.exception("Failed to process document %s", document_id)
            await session.execute(
                text("UPDATE roadmap_documents SET status = 'failed' WHERE id = :doc_id"), {"doc_id": document_id}
            )
            await session.commit()
            raise

    async def _store_document_chunks(self, session: AsyncSession, document_id: int, chunks: list[str]) -> None:
        """Store document chunks with embeddings using txtai's native index method.

        With pgvector backend, txtai handles:
        - Embedding generation (via our LiteLLM transform)
        - Vector storage in pgvector
        - Content/metadata storage in PostgreSQL
        - Automatic indexing and optimization

        Based on: https://neuml.github.io/txtai/embeddings/#index
        """
        try:
            # Get document metadata
            result = await session.execute(
                text("""
                    SELECT id, roadmap_id as course_id, title, document_type
                    FROM roadmap_documents
                    WHERE id = :doc_id
                """),
                {"doc_id": document_id},
            )
            doc_info = result.fetchone()

            if not doc_info:
                msg = f"Document {document_id} not found"
                raise ValueError(msg)

            # Generate consistent UUID for document
            doc_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, f"course_document_{document_id}")

            # Prepare documents for txtai indexing
            # Format based on: https://neuml.github.io/txtai/embeddings/#index
            documents = []
            for i, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue

                # txtai expects: (id, data, tags) tuple
                # When data is a dict, "text" key contains the content to embed
                doc_id = f"{doc_uuid}_{i}"

                # Tags for filtering (txtai uses these for search filtering)
                tags = f"course:{doc_info.course_id} doc:{document_id} type:{doc_info.document_type}"

                # Data dictionary with text and metadata
                # txtai will store this in PostgreSQL content tables
                data = {
                    "text": chunk,  # Required: text to embed
                    "document_id": document_id,
                    "course_id": str(doc_info.course_id),
                    "title": doc_info.title,
                    "document_type": doc_info.document_type,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                }
                documents.append((doc_id, data, tags))

            if not documents:
                logger.warning("No valid chunks to index for document %s", document_id)
                return

            # Use VectorRAG directly for storing embeddings
            # It already handles LiteLLM + pgvector perfectly
            logger.info("Storing %s chunks for document %s using VectorRAG with pgvector", len(chunks), document_id)

            # Get VectorRAG instance
            if not hasattr(self, "_vector_rag"):
                from src.ai.rag.embeddings import VectorRAG

                self._vector_rag = VectorRAG()

            # Use VectorRAG's existing method to store chunks with embeddings
            await self._vector_rag.store_document_chunks_with_embeddings(
                session=session,
                document_id=document_id,
                course_id=doc_info.course_id,
                title=doc_info.title,
                chunks=chunks,
            )

            logger.info("Successfully stored %s chunks for document %s in pgvector", len(chunks), document_id)

        except Exception:
            logger.exception("Failed to store document chunks")
            raise

    async def search_documents(
        self, session: AsyncSession, user_id: uuid.UUID, course_id: uuid.UUID, query: str, top_k: int | None = None
    ) -> list[SearchResult]:
        """Search documents in a course."""
        # Validate user owns the course
        await self.validate_course_ownership(session, course_id, user_id)
        return await self._search_roadmap_documents(session, course_id, query, top_k)

    async def _search_roadmap_documents(
        self, session: AsyncSession, course_id: uuid.UUID, query: str, top_k: int | None = None
    ) -> list[SearchResult]:
        """Search documents using VectorRAG's existing pgvector search.

        Why complicate things? VectorRAG already has a perfect search method!
        """
        try:
            if top_k is None:
                top_k = self.config.rerank_k

            # Get VectorRAG instance
            if not hasattr(self, "_vector_rag"):
                from src.ai.rag.embeddings import VectorRAG

                self._vector_rag = VectorRAG()

            # Use VectorRAG's existing search method
            return await self._vector_rag.search_course_documents_vector(
                session=session, course_id=course_id, query=query, limit=top_k
            )

        except Exception:
            logger.exception("Failed to search documents")
            return []

    async def get_documents(
        self, session: AsyncSession, user_id: uuid.UUID, course_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> list[DocumentResponse]:
        """Get documents for a course."""
        # Validate user owns the course
        await self.validate_course_ownership(session, course_id, user_id)

        try:
            result = await session.execute(
                text("""
                    SELECT rd.* FROM roadmap_documents rd
                    JOIN roadmaps r ON rd.roadmap_id = r.id
                    WHERE rd.roadmap_id = :course_id AND r.user_id = :user_id
                    ORDER BY rd.created_at DESC
                    LIMIT :limit OFFSET :skip
                """),
                {"course_id": str(course_id), "user_id": str(user_id), "limit": limit, "skip": skip},
            )

            docs = []
            for row in result.fetchall():
                row_dict = row._asdict()
                docs.append(
                    DocumentResponse(
                        id=row_dict["id"],
                        course_id=row_dict["roadmap_id"],  # Maps to course_id field
                        title=row_dict["title"],
                        source_url=row_dict.get("source_url"),
                        document_type=row_dict["document_type"],
                        file_path=row_dict.get("file_path"),
                        url=row_dict.get("url"),
                        crawl_date=row_dict.get("crawl_date"),
                        content_hash=row_dict.get("content_hash"),
                        doc_metadata=row_dict.get("metadata"),
                        status=row_dict["status"],
                        created_at=row_dict["created_at"],
                        processed_at=row_dict.get("processed_at"),
                        embedded_at=row_dict.get("embedded_at"),
                    )
                )
            return docs
        except Exception:
            logger.exception("Failed to get documents")
            # Return empty list instead of crashing
            return []

    async def count_documents(self, session: AsyncSession, user_id: uuid.UUID, course_id: uuid.UUID) -> int:
        """Count documents for a course."""
        # Validate user owns the course
        await self.validate_course_ownership(session, course_id, user_id)

        try:
            result = await session.execute(
                text("""
                    SELECT COUNT(*) FROM roadmap_documents rd
                    JOIN roadmaps r ON rd.roadmap_id = r.id
                    WHERE rd.roadmap_id = :course_id AND r.user_id = :user_id
                """),
                {"course_id": str(course_id), "user_id": str(user_id)},
            )
            return result.scalar_one_or_none() or 0
        except Exception:
            logger.exception("Failed to count documents")
            return 0

    async def delete_document(self, session: AsyncSession, user_id: uuid.UUID, document_id: int) -> None:
        """Delete a document and its chunks."""
        try:
            # First check if document exists and user owns it
            result = await session.execute(
                text("""
                    SELECT rd.id, rd.file_path, rd.roadmap_id
                    FROM roadmap_documents rd
                    JOIN roadmaps r ON rd.roadmap_id = r.id
                    WHERE rd.id = :doc_id AND r.user_id = :user_id
                """),
                {"doc_id": document_id, "user_id": str(user_id)},
            )
            doc = result.fetchone()

            if not doc:
                msg = f"Document {document_id} not found"
                raise ValueError(msg)

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
            chunks_result = await session.execute(
                text("DELETE FROM rag_document_chunks WHERE doc_id = :doc_uuid AND doc_type = 'course'"),
                {"doc_uuid": str(doc_uuid)},
            )
            chunks_deleted = chunks_result.rowcount
            if chunks_deleted > 0:
                logger.info(f"Deleted {chunks_deleted} RAG chunks for document {document_id}")

            # Delete document
            await session.execute(text("DELETE FROM roadmap_documents WHERE id = :doc_id"), {"doc_id": document_id})

            await session.commit()
            logger.info("Successfully deleted document %s", document_id)

        except Exception:
            await session.rollback()
            logger.exception("Failed to delete document %s", document_id)
            raise

    @staticmethod
    async def validate_course_ownership(
        session: AsyncSession,
        course_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Validate that the user owns the course."""
        result = await session.execute(
            text("SELECT id FROM roadmaps WHERE id = :course_id AND user_id = :user_id"),
            {"course_id": str(course_id), "user_id": str(user_id)},
        )
        if not result.fetchone():
            raise HTTPException(status_code=404, detail="Course not found or access denied")

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
            rowcount = result.rowcount

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
            rowcount = result.rowcount

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
