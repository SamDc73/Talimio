"""RAG system service layer - FIXED VERSION with proper lazy initialization."""

import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.rag.chunker import ChunkerFactory
from src.ai.rag.ingest import DocumentProcessor
from src.ai.rag.retriever import DocumentRetriever
from src.ai.rag.schemas import DocumentResponse, SearchResult
from src.ai.rag.vector_store import VectorStore
from src.config import env
from src.courses.models import RoadmapDocument


logger = logging.getLogger(__name__)


class RAGService:
    """Lightweight RAG service orchestrator using modular components - FIXED."""

    # Singleton instance
    _instance: Optional["RAGService"] = None
    _initialized = False

    # Supported file types with their MIME types
    SUPPORTED_FILE_TYPES = {
        ".pdf": ["application/pdf"],
        ".txt": ["text/plain"],
        ".md": ["text/markdown", "text/x-markdown", "text/plain"],
        ".epub": ["application/epub+zip"],
        ".docx": ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
    }

    def __new__(cls) -> "RAGService":
        """Singleton pattern to prevent multiple initializations."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize RAG service - lazy initialization of components."""
        if not self._initialized:
            # Store config but don't create components yet
            self.max_file_size_mb = int(env("RAG_MAX_FILE_SIZE_MB", "50"))
            self.max_file_size_bytes = self.max_file_size_mb * 1024 * 1024

            # Components will be created on first use
            self._document_processor: DocumentProcessor | None = None
            self._chunker = None
            self._vector_store: VectorStore | None = None
            self._retriever: DocumentRetriever | None = None

            self._initialized = True

    @property
    def document_processor(self) -> DocumentProcessor:
        """Lazy load document processor."""
        if self._document_processor is None:
            self._document_processor = DocumentProcessor()
        return self._document_processor

    @property
    def chunker(self) -> ChunkerFactory:
        """Lazy load chunker."""
        if self._chunker is None:
            self._chunker = ChunkerFactory.get_default_chunker()
        return self._chunker

    @property
    def vector_store(self) -> VectorStore:
        """Lazy load vector store."""
        if self._vector_store is None:
            self._vector_store = VectorStore()
        return self._vector_store

    @property
    def retriever(self) -> DocumentRetriever:
        """Lazy load retriever."""
        if self._retriever is None:
            self._retriever = DocumentRetriever()
        return self._retriever

    def _validate_file_type(self, filename: str) -> str:
        """Validate file type and return the detected extension."""
        if not filename:
            raise HTTPException(status_code=400, detail="Filename is required")

        # Get file extension
        file_path = Path(filename.lower())
        extension = file_path.suffix

        if extension not in self.SUPPORTED_FILE_TYPES:
            supported_exts = ", ".join(self.SUPPORTED_FILE_TYPES.keys())
            raise HTTPException(
                status_code=400, detail=f"Unsupported file type '{extension}'. Supported formats: {supported_exts}"
            )

        return extension

    @staticmethod
    def _detect_mime_from_content(file_content: bytes) -> str | None:
        """Detect MIME type from file content using magic bytes."""
        if not file_content:
            return None

        # Simple PDF detection
        if file_content.startswith(b"%PDF"):
            return "application/pdf"

        return None

    async def upload_document(
        self,
        session: AsyncSession,
        roadmap_id: uuid.UUID,
        document_type: str,
        title: str,
        file_content: bytes | None = None,
        url: str | None = None,
        filename: str | None = None,
    ) -> DocumentResponse:
        """Upload a document to a roadmap."""
        try:
            # Create document record
            doc = RoadmapDocument(
                roadmap_id=roadmap_id,
                title=title,
                source_url=url,
                document_type=document_type,
                status="pending",  # Start as pending for processing
            )
            session.add(doc)
            await session.flush()

            # Store file if provided
            if file_content and filename:
                from src.config.settings import get_settings

                settings = get_settings()
                upload_dir = Path(settings.LOCAL_STORAGE_PATH) / "documents" / str(roadmap_id)
                upload_dir.mkdir(parents=True, exist_ok=True)

                file_path = upload_dir / f"{doc.id}_{filename}"
                file_path.write_bytes(file_content)

                doc.file_path = str(file_path)

            await session.commit()

            # Process document asynchronously
            import asyncio

            asyncio.create_task(self._process_document_async(doc.id))  # noqa: RUF006

            return DocumentResponse.model_validate(doc.__dict__)

        except Exception as e:
            await session.rollback()
            logger.exception("Failed to upload document")
            raise HTTPException(status_code=500, detail=str(e)) from e

    async def _process_document_async(self, document_id: int) -> None:
        """Process document in background task."""
        try:
            # Import here to avoid circular imports
            from src.database.session import async_session_maker

            async with async_session_maker() as session:
                await self.process_document(session, document_id)
        except Exception:
            logger.exception("Failed to process document %s in background", document_id)

    async def process_document(self, session: AsyncSession, document_id: int) -> None:
        """Process a document (extract text, chunk, embed)."""
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

            # Extract text based on document type
            text_content = ""
            if doc_dict["document_type"] == "url" and doc_dict["source_url"]:
                # Process URL
                text_content, crawl_date = await self.document_processor.process_url_document(doc_dict["source_url"])
                await session.execute(
                    text("UPDATE roadmap_documents SET crawl_date = :crawl_date WHERE id = :doc_id"),
                    {"crawl_date": crawl_date, "doc_id": document_id},
                )
            elif doc_dict["file_path"]:
                # Process file
                text_content = await self.document_processor.process_document(
                    doc_dict["file_path"], doc_dict["document_type"]
                )
            else:
                msg = "No file path or URL to process"
                raise ValueError(msg)

            # Chunk the text
            chunks = self.chunker.chunk_text(text_content)
            logger.info("Document %s chunked into %s pieces", document_id, len(chunks))

            # Store chunks with embeddings
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
        """Store document chunks with embeddings."""
        try:
            # Get document metadata for the UUID and roadmap_id
            result = await session.execute(
                text("""
                    SELECT id, roadmap_id, title, document_type
                    FROM roadmap_documents
                    WHERE id = :doc_id
                """),
                {"doc_id": document_id},
            )
            doc_info = result.fetchone()

            if not doc_info:
                msg = f"Document {document_id} not found"
                raise ValueError(msg)

            # Generate a UUID based on the integer ID for consistency
            # This ensures the same document always gets the same UUID
            doc_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, f"roadmap_document_{document_id}")

            # Prepare metadata
            metadata = {
                "original_document_id": document_id,
                "roadmap_id": str(doc_info.roadmap_id),
                "document_title": doc_info.title,
                "document_type": doc_info.document_type,
            }

            # Use VectorStore to store chunks
            await self.vector_store.store_chunks_with_embeddings(
                session=session, doc_id=doc_uuid, doc_type="course", chunks=chunks, metadata=metadata
            )

            logger.info("Stored %s chunks for document %s", len(chunks), document_id)

        except Exception:
            logger.exception("Failed to store document chunks")
            raise

    async def search_documents(
        self, session: AsyncSession, roadmap_id: uuid.UUID, query: str, top_k: int | None = None
    ) -> list[SearchResult]:
        """Search documents using the modular retriever."""
        try:
            # Use the retriever to search for relevant chunks
            return await self.retriever.search_documents(
                session=session, roadmap_id=roadmap_id, query=query, top_k=top_k or 5
            )
        except Exception:
            logger.exception("Failed to search documents")
            return []

    async def get_document_context(
        self, _session: AsyncSession, _roadmap_id: uuid.UUID, _query: str, _max_chunks: int = 5
    ) -> str:
        """Get relevant document context for AI tasks."""
        # For now, return empty context
        return ""

    @staticmethod
    async def get_documents(
        session: AsyncSession, roadmap_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> list[DocumentResponse]:
        """Get documents for a roadmap."""
        try:
            result = await session.execute(
                text("""
                    SELECT * FROM roadmap_documents
                    WHERE roadmap_id = :roadmap_id
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :skip
                """),
                {"roadmap_id": str(roadmap_id), "limit": limit, "skip": skip},
            )

            docs = []
            for row in result.fetchall():
                row_dict = row._asdict()
                docs.append(
                    DocumentResponse(
                        id=row_dict["id"],
                        roadmap_id=row_dict["roadmap_id"],
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

    @staticmethod
    async def count_documents(session: AsyncSession, roadmap_id: uuid.UUID) -> int:
        """Count documents for a roadmap."""
        try:
            result = await session.execute(
                text("""
                    SELECT COUNT(*) FROM roadmap_documents
                    WHERE roadmap_id = :roadmap_id
                """),
                {"roadmap_id": str(roadmap_id)},
            )
            return result.scalar_one_or_none() or 0
        except Exception:
            logger.exception("Failed to count documents")
            return 0

    @staticmethod
    async def delete_document(session: AsyncSession, document_id: int) -> None:
        """Delete a document and its chunks."""
        try:
            # First check if document exists
            result = await session.execute(
                text("SELECT id, file_path FROM roadmap_documents WHERE id = :doc_id"), {"doc_id": document_id}
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
            # and are handled by the new system

            # Delete document
            await session.execute(text("DELETE FROM roadmap_documents WHERE id = :doc_id"), {"doc_id": document_id})

            await session.commit()
            logger.info("Successfully deleted document %s", document_id)

        except Exception:
            await session.rollback()
            logger.exception("Failed to delete document %s", document_id)
            raise
