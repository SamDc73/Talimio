"""RAG system service layer - lightweight orchestrator."""

import mimetypes
import os
import uuid
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.rag.chunker import ChunkerFactory
from src.ai.rag.ingest import DocumentProcessor
from src.ai.rag.retriever import DocumentRetriever
from src.ai.rag.schemas import DocumentResponse, SearchResult
from src.ai.rag.vector_store import VectorStore
from src.courses.models import RoadmapDocument


class RAGService:
    """Lightweight RAG service orchestrator using modular components."""

    # Supported file types with their MIME types
    SUPPORTED_FILE_TYPES = {
        ".pdf": ["application/pdf"],
        ".txt": ["text/plain"],
        ".md": ["text/markdown", "text/x-markdown", "text/plain"],
        ".epub": ["application/epub+zip"],
        ".docx": ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
    }

    def __init__(self) -> None:
        """Initialize RAG service with component instances."""
        self.document_processor = DocumentProcessor()
        self.chunker = ChunkerFactory.get_default_chunker()
        self.vector_store = VectorStore()
        self.retriever = DocumentRetriever()

        # Get file size limit from environment (default 50MB)
        self.max_file_size_mb = int(os.getenv("RAG_MAX_FILE_SIZE_MB", "50"))
        self.max_file_size_bytes = self.max_file_size_mb * 1024 * 1024

    def _validate_file_type(self, filename: str, file_content: bytes | None = None) -> str:
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

        # MIME type validation if file content is provided
        if file_content:
            # Detect MIME type from content
            detected_mime = mimetypes.guess_type(filename)[0]

            # For files without clear MIME detection, check magic bytes
            if not detected_mime:
                detected_mime = self._detect_mime_from_content(file_content)

            if detected_mime and detected_mime not in self.SUPPORTED_FILE_TYPES[extension]:
                raise HTTPException(
                    status_code=400,
                    detail=f"File content does not match expected type for {extension} files. Detected: {detected_mime}",
                )

        return extension

    def _detect_mime_from_content(self, file_content: bytes) -> str | None:
        """Detect MIME type from file content using magic bytes."""
        if not file_content:
            return None

        mime_type = None

        # PDF magic bytes
        if file_content.startswith(b"%PDF"):
            mime_type = "application/pdf"
        # ZIP-based formats (EPUB, DOCX)
        elif file_content.startswith((b"PK\x03\x04", b"PK\x05\x06")):
            # Further differentiate between EPUB and DOCX by checking internal structure
            if b"mimetype" in file_content[:1000] and b"application/epub+zip" in file_content[:1000]:
                mime_type = "application/epub+zip"
            elif b"word/" in file_content[:1000] or b"[Content_Types].xml" in file_content[:1000]:
                mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            else:
                mime_type = "application/zip"
        else:
            # Text files - check if content is valid UTF-8
            try:
                file_content.decode("utf-8")
                mime_type = "text/plain"
            except UnicodeDecodeError:
                pass

        return mime_type

    def _validate_file_size(self, file_content: bytes) -> None:
        """Validate file size against configured limits."""
        if len(file_content) > self.max_file_size_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File size ({len(file_content) / 1024 / 1024:.1f}MB) exceeds maximum allowed size ({self.max_file_size_mb}MB)",
            )

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
        """Upload and store a document for processing."""
        # Validate file upload if file content is provided
        if file_content:
            if not filename:
                raise HTTPException(status_code=400, detail="Filename is required for file uploads")

            # Validate file size
            self._validate_file_size(file_content)

            # Validate file type and get extension
            extension = self._validate_file_type(filename, file_content)

            # Update document_type based on validated extension
            document_type = extension.lstrip(".")

        # Create document record
        doc = RoadmapDocument(
            roadmap_id=roadmap_id, document_type=document_type, title=title, url=url, status="pending"
        )

        if file_content:
            try:
                # Save file using document processor
                if document_type == "pdf":
                    file_path, content_hash = self.document_processor.save_pdf_file(file_content)
                else:
                    # For other file types, we'll extend the document processor
                    file_path, content_hash = self.document_processor.save_file(file_content, filename)

                doc.file_path = file_path
                doc.content_hash = content_hash
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to process file: {e!s}") from e

        session.add(doc)
        await session.commit()
        await session.refresh(doc)

        # Create response without the metadata field for now
        return DocumentResponse(
            id=doc.id,
            roadmap_id=doc.roadmap_id,
            document_type=doc.document_type,
            title=doc.title,
            file_path=doc.file_path,
            url=doc.url,
            source_url=doc.source_url,
            crawl_date=doc.crawl_date,
            content_hash=doc.content_hash,
            created_at=doc.created_at,
            processed_at=doc.processed_at,
            embedded_at=doc.embedded_at,
            status=doc.status,
            doc_metadata=doc.doc_metadata if hasattr(doc, "doc_metadata") else None,
        )

    async def process_document(self, session: AsyncSession, document_id: int) -> None:
        """Process a document and generate embeddings using modular components."""
        # Get document
        result = await session.execute(
            text("SELECT * FROM roadmap_documents WHERE id = :doc_id"), {"doc_id": document_id}
        )
        doc_row = result.fetchone()
        if not doc_row:
            msg = f"Document {document_id} not found"
            raise ValueError(msg)

        try:
            # Update status to processing
            await session.execute(
                text("UPDATE roadmap_documents SET status = 'processing', processed_at = NOW() WHERE id = :doc_id"),
                {"doc_id": document_id},
            )
            await session.commit()

            # Process document using appropriate ingestor
            if doc_row.file_path:
                # File-based document
                try:
                    text_content = await self.document_processor.process_document(
                        doc_row.file_path, doc_row.document_type
                    )
                except ValueError as e:
                    # Re-raise as more specific error for better error handling
                    msg = f"Failed to process {doc_row.document_type} file: {e!s}"
                    raise ValueError(msg) from e
            else:
                # URL-based document
                text_content, crawl_date = await self.document_processor.process_url_document(doc_row.url)
                await session.execute(
                    text("UPDATE roadmap_documents SET crawl_date = :crawl_date WHERE id = :doc_id"),
                    {"crawl_date": crawl_date, "doc_id": document_id},
                )

            # Store parsed content
            await session.execute(
                text("UPDATE roadmap_documents SET parsed_content = :content WHERE id = :doc_id"),
                {"content": text_content, "doc_id": document_id},
            )

            # Chunk text using modular chunker
            chunks = self.chunker.chunk_text(text_content)

            # Store chunks with embeddings using vector store
            await self.vector_store.store_chunks_with_embeddings(session, document_id, chunks)

            # Update status to embedded
            await session.execute(
                text("UPDATE roadmap_documents SET status = 'embedded', embedded_at = NOW() WHERE id = :doc_id"),
                {"doc_id": document_id},
            )
            await session.commit()

        except Exception:
            # Update status to failed
            await session.execute(
                text("UPDATE roadmap_documents SET status = 'failed' WHERE id = :doc_id"), {"doc_id": document_id}
            )
            await session.commit()
            raise

    async def search_documents(
        self, session: AsyncSession, roadmap_id: uuid.UUID, query: str, top_k: int | None = None
    ) -> list[SearchResult]:
        """Search documents using the modular retriever."""
        return await self.retriever.search_documents(session=session, roadmap_id=roadmap_id, query=query, top_k=top_k)

    async def get_document_context(
        self, session: AsyncSession, roadmap_id: uuid.UUID, query: str, max_chunks: int = 5
    ) -> str:
        """Get relevant document context for AI tasks."""
        return await self.retriever.get_document_context(
            session=session, roadmap_id=roadmap_id, query=query, max_chunks=max_chunks
        )

    async def get_documents(
        self, session: AsyncSession, roadmap_id: uuid.UUID, skip: int = 0, limit: int = 20
    ) -> list[DocumentResponse]:
        """Get documents for a roadmap."""
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
                    document_type=row_dict["document_type"],
                    title=row_dict["title"],
                    file_path=row_dict.get("file_path"),
                    url=row_dict.get("url"),
                    source_url=row_dict.get("source_url"),
                    crawl_date=row_dict.get("crawl_date"),
                    content_hash=row_dict.get("content_hash"),
                    created_at=row_dict["created_at"],
                    processed_at=row_dict.get("processed_at"),
                    embedded_at=row_dict.get("embedded_at"),
                    status=row_dict["status"],
                    doc_metadata=row_dict.get("doc_metadata"),
                )
            )
        return docs

    async def delete_document(self, session: AsyncSession, document_id: int) -> None:
        """Delete a document and its associated files."""
        # Get document to check for file path
        result = await session.execute(
            text("SELECT file_path FROM roadmap_documents WHERE id = :doc_id"), {"doc_id": document_id}
        )
        row = result.fetchone()

        if row and row.file_path:
            # Delete physical file
            file_path = Path(row.file_path)
            if file_path.exists():
                file_path.unlink()

        # Delete from database (cascades to chunks)
        await session.execute(text("DELETE FROM roadmap_documents WHERE id = :doc_id"), {"doc_id": document_id})
        await session.commit()
