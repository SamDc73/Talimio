"""Text chunking strategies and implementations."""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
from uuid import UUID

import pymupdf

from src.ai.constants import rag_config


logger = logging.getLogger(__name__)


class DocumentChunk:
    """Represents a document chunk with metadata."""

    def __init__(self, content: str, chunk_index: int, metadata: dict[str, Any] | None = None) -> None:
        self.content = content
        self.chunk_index = chunk_index
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert chunk to dictionary representation."""
        return {"content": self.content, "chunk_index": self.chunk_index, "metadata": self.metadata}


class BaseChunker(ABC):
    """Abstract base class for text chunking strategies."""

    @abstractmethod
    def chunk_text(self, text: str) -> list[str]:
        """Split text into chunks."""


class EnhancedChunker(ABC):
    """Base class for enhanced document chunking with semantic boundaries."""

    def __init__(self, chunk_size: int | None = None, chunk_overlap: int | None = None) -> None:
        self.chunk_size = chunk_size or rag_config.chunk_size
        self.chunk_overlap = chunk_overlap or rag_config.chunk_overlap

    @abstractmethod
    def chunk_document(self, doc_id: UUID, doc_type: str, content: str | Path) -> list[DocumentChunk]:
        """Chunk document content with semantic boundaries."""


class BasicChunker(BaseChunker, EnhancedChunker):
    """Simple word-based text chunking with overlap."""

    def __init__(self, chunk_size: int | None = None, chunk_overlap: int | None = None) -> None:
        """Initialize chunker with optional custom sizes."""
        super().__init__(chunk_size, chunk_overlap)
        self.words_per_chunk = int(self.chunk_size * 0.75)  # Rough token estimation
        self.words_overlap = int(self.chunk_overlap * 0.75)

    def chunk_text(self, text: str) -> list[str]:
        """Split text into overlapping word-based chunks."""
        words = text.split()
        chunks = []

        for i in range(0, len(words), self.words_per_chunk - self.words_overlap):
            chunk_words = words[i : i + self.words_per_chunk]
            if chunk_words:
                chunks.append(" ".join(chunk_words))

        return chunks

    def chunk_document(self, _doc_id: UUID, doc_type: str, content: str | Path) -> list[DocumentChunk]:
        """Chunk document using basic word-based chunking."""
        text = str(content) if not isinstance(content, Path) else content.read_text()
        chunks = self.chunk_text(text)

        document_chunks = []
        for i, chunk_content in enumerate(chunks):
            metadata = {"chunk_type": "basic", "doc_type": doc_type}
            document_chunks.append(DocumentChunk(chunk_content, i, metadata))

        return document_chunks


class BookChunker(EnhancedChunker):
    """Specialized chunker for book PDFs with chapter awareness."""

    def __init__(self, chunk_size: int | None = None, chunk_overlap: int | None = None) -> None:
        super().__init__(chunk_size, chunk_overlap)

    def chunk_document(self, doc_id: UUID, doc_type: str, content: str | Path) -> list[DocumentChunk]:
        """Chunk book PDF with chapter awareness."""
        if not isinstance(content, Path) or not content.exists():
            logger.error("Invalid file path for book %s", doc_id)
            return []

        try:
            doc = pymupdf.open(str(content))
            document_chunks = []
            chunk_index = 0

            # Extract TOC for chapter information
            toc = doc.get_toc()
            chapter_info = self._process_toc(toc)

            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()

                if not text.strip():
                    continue

                # Get current chapter
                current_chapter = self._get_chapter_for_page(page_num + 1, chapter_info)

                # Chunk the page text
                page_chunks = self._chunk_page_text(text, self.chunk_size, self.chunk_overlap)

                for chunk_content in page_chunks:
                    metadata = {
                        "chunk_type": "book",
                        "doc_type": doc_type,
                        "page": page_num + 1,
                        "chapter": current_chapter.get("title", "Unknown"),
                        "chapter_level": current_chapter.get("level", 0),
                    }
                    document_chunks.append(DocumentChunk(chunk_content, chunk_index, metadata))
                    chunk_index += 1

            doc.close()
            logger.info("Chunked book %s into %s chunks with chapter awareness", doc_id, len(document_chunks))
            return document_chunks

        except Exception:
            logger.exception("Failed to chunk book %s", doc_id)
            # Fallback to basic chunking
            basic_chunker = BasicChunker(self.chunk_size, self.chunk_overlap)
            return basic_chunker.chunk_document(doc_id, doc_type, content)

    def _process_toc(self, toc: list) -> list[dict]:
        """Process table of contents into structured format."""
        chapters = []
        for level, title, page in toc:
            chapters.append({"level": level, "title": title, "page": page})
        return chapters

    def _get_chapter_for_page(self, page_num: int, chapters: list[dict]) -> dict:
        """Find which chapter a page belongs to."""
        current_chapter = {"title": "Introduction", "level": 0}

        for chapter in chapters:
            if chapter["page"] <= page_num:
                current_chapter = chapter
            else:
                break

        return current_chapter

    def _chunk_page_text(self, text: str, chunk_size: int, overlap: int) -> list[str]:
        """Chunk page text with overlap."""
        words = text.split()
        words_per_chunk = int(chunk_size * 0.75)
        words_overlap = int(overlap * 0.75)
        chunks = []

        for i in range(0, len(words), words_per_chunk - words_overlap):
            chunk_words = words[i : i + words_per_chunk]
            if chunk_words:
                chunks.append(" ".join(chunk_words))

        return chunks


class ChunkerFactory:
    """Factory class for creating appropriate chunker instances."""

    @staticmethod
    def create_chunker(
        doc_type: str,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        _metadata: dict[str, Any] | None = None,
    ) -> EnhancedChunker:
        """Create appropriate chunker for document type."""
        if doc_type == "book":
            return BookChunker(chunk_size, chunk_overlap)
        if doc_type in ["video", "article", "web"]:
            # Use basic chunking for all these types
            return BasicChunker(chunk_size, chunk_overlap)
        # Default to basic chunking
        return BasicChunker(chunk_size, chunk_overlap)

    @staticmethod
    def get_default_chunker() -> EnhancedChunker:
        """Get the default chunker (basic for now)."""
        return BasicChunker()
