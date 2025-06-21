"""RAG system service layer - lightweight orchestrator."""

import uuid
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.rag.chunker import ChunkerFactory
from src.ai.rag.ingest import DocumentProcessor
from src.ai.rag.retriever import DocumentRetriever
from src.ai.rag.schemas import DocumentResponse, SearchResult
from src.ai.rag.vector_store import VectorStore
from src.roadmaps.models import RoadmapDocument


class RAGService:
    """Lightweight RAG service orchestrator using modular components."""

    def __init__(self) -> None:
        """Initialize RAG service with component instances."""
        self.document_processor = DocumentProcessor()
        self.chunker = ChunkerFactory.get_default_chunker()
        self.vector_store = VectorStore()
        self.retriever = DocumentRetriever()

    async def upload_document(
        self,
        session: AsyncSession,
        roadmap_id: uuid.UUID,
        document_type: str,
        title: str,
        file_content: bytes | None = None,
        url: str | None = None,
    ) -> DocumentResponse:
        """Upload and store a document for processing."""
        # Create document record
        doc = RoadmapDocument(
            roadmap_id=roadmap_id, document_type=document_type, title=title, url=url, status="pending"
        )

        if file_content and document_type == "pdf":
            # Save PDF file using document processor
            file_path, content_hash = self.document_processor.save_pdf_file(file_content)
            doc.file_path = file_path
            doc.content_hash = content_hash

        session.add(doc)
        await session.commit()
        await session.refresh(doc)

        return DocumentResponse.model_validate(doc)

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
            if doc_row.document_type == "pdf":
                markdown_content = await self.document_processor.process_pdf_document(doc_row.file_path)
            else:  # url
                markdown_content, crawl_date = await self.document_processor.process_url_document(doc_row.url)
                await session.execute(
                    text("UPDATE roadmap_documents SET crawl_date = :crawl_date WHERE id = :doc_id"),
                    {"crawl_date": crawl_date, "doc_id": document_id},
                )

            # Store parsed content
            await session.execute(
                text("UPDATE roadmap_documents SET parsed_content = :content WHERE id = :doc_id"),
                {"content": markdown_content, "doc_id": document_id},
            )

            # Chunk text using modular chunker
            chunks = self.chunker.chunk_text(markdown_content)

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

        return [DocumentResponse.model_validate(dict(row)) for row in result.fetchall()]

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
