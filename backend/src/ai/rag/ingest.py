"""Document ingestion and processing components."""

import hashlib
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import ebooklib
import fitz  # PyMuPDF
from bs4 import BeautifulSoup
from docx import Document
from ebooklib import epub
from goose3 import Goose
from sqlalchemy import select

from src.ai.constants import rag_config
from src.ai.rag.chunker import ChunkerFactory
from src.ai.rag.vector_store import VectorStore
from src.books.models import Book
from src.database.session import async_session_maker


logger = logging.getLogger(__name__)

class BaseIngestor:
    """Base class for document ingestors with common functionality."""

    def save_file_base(self, file_content: bytes, extension: str) -> tuple[str, str]:
        """Save binary file with given extension and return path and content hash."""
        # Generate unique filename
        file_id = str(uuid.uuid4())
        file_path = rag_config.upload_dir / f"{file_id}.{extension}"

        # Save file
        with file_path.open("wb") as f:
            f.write(file_content)

        # Generate content hash for deduplication
        content_hash = hashlib.sha256(file_content).hexdigest()

        return str(file_path), content_hash


class PDFIngestor(BaseIngestor):
    """Extract text from PDF documents."""

    async def process_pdf(self, file_path: str) -> str:
        """Extract text from PDF and convert to markdown-like format."""
        doc = fitz.open(file_path)
        text_content = ""

        for page in doc:
            text_content += page.get_text()

        doc.close()
        return text_content

    def save_file(self, file_content: bytes) -> tuple[str, str]:
        """Save PDF file to disk and return path and content hash."""
        return self.save_file_base(file_content, "pdf")


class TextIngestor(BaseIngestor):
    """Extract text from plain text and markdown files."""

    async def process_text(self, file_path: str) -> str:
        """Extract text from text/markdown files."""
        path = Path(file_path)
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Fallback to other encodings
            for encoding in ["latin-1", "cp1252"]:
                try:
                    return path.read_text(encoding=encoding)
                except UnicodeDecodeError:
                    continue
            msg = f"Unable to decode text file: {file_path}"
            raise ValueError(msg) from None

    def save_file(self, file_content: bytes, filename: str) -> tuple[str, str]:
        """Save text file to disk and return path and content hash."""
        # Generate unique filename preserving extension
        file_id = str(uuid.uuid4())
        original_ext = Path(filename).suffix
        file_path = rag_config.upload_dir / f"{file_id}{original_ext}"

        # Save file
        try:
            # Try UTF-8 first
            text_content = file_content.decode("utf-8")
            with file_path.open("w", encoding="utf-8") as f:
                f.write(text_content)
        except UnicodeDecodeError:
            # Fallback to binary write
            with file_path.open("wb") as f:
                f.write(file_content)

        # Generate content hash for deduplication
        content_hash = hashlib.sha256(file_content).hexdigest()

        return str(file_path), content_hash


class EPUBIngestor(BaseIngestor):
    """Extract text from EPUB documents."""

    async def process_epub(self, file_path: str) -> str:
        """Extract text from EPUB and convert to readable format."""
        try:
            book = epub.read_epub(file_path)
            text_content = ""

            # Extract title and author info
            title = book.get_metadata("DC", "title")
            if title:
                text_content += f"Title: {title[0][0]}\n\n"

            # Extract text from all chapters
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    soup = BeautifulSoup(item.get_content(), "html.parser")
                    chapter_text = soup.get_text().strip()
                    if chapter_text:
                        text_content += chapter_text + "\n\n"

            return text_content
        except Exception as e:
            msg = f"Failed to process EPUB file: {e!s}"
            raise ValueError(msg) from e

    def save_file(self, file_content: bytes, _filename: str) -> tuple[str, str]:
        """Save EPUB file to disk and return path and content hash."""
        return self.save_file_base(file_content, "epub")


class DOCXIngestor(BaseIngestor):
    """Extract text from DOCX documents."""

    async def process_docx(self, file_path: str) -> str:
        """Extract text from DOCX and convert to readable format."""
        try:
            doc = Document(file_path)
            text_content = ""

            # Extract all paragraphs
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_content += paragraph.text + "\n"

            return text_content
        except Exception as e:
            msg = f"Failed to process DOCX file: {e!s}"
            raise ValueError(msg) from e

    def save_file(self, file_content: bytes, _filename: str) -> tuple[str, str]:
        """Save DOCX file to disk and return path and content hash."""
        return self.save_file_base(file_content, "docx")


class URLIngestor:
    """Extract clean content from web URLs."""

    def __init__(self) -> None:
        """Initialize URLIngestor with Goose3 configuration."""
        self.goose = Goose()

    async def process_url(self, url: str) -> tuple[str, datetime]:
        """Extract clean webpage content as plain text using Goose3."""
        # Goose3 is synchronous, so we'll run it in the current thread
        # For production use, consider running in executor for true async
        article = self.goose.extract(url=url)

        # Get clean text content from the article
        clean_text = article.cleaned_text

        # Extract title and prepend it to the content for context
        if article.title:
            clean_text = f"Title: {article.title}\n\n{clean_text}"

        crawl_date = datetime.now(tz=UTC)

        return clean_text, crawl_date

    def extract_title_from_url(self, url: str) -> str:
        """Extract just the title from a URL."""
        try:
            article = self.goose.extract(url=url)
            return article.title if article.title else "Untitled Document"
        except Exception:
            return "Untitled Document"


class DocumentProcessor:
    """Orchestrate document processing pipeline."""

    def __init__(self) -> None:
        """Initialize document processor with ingestors."""
        self.pdf_ingestor = PDFIngestor()
        self.text_ingestor = TextIngestor()
        self.epub_ingestor = EPUBIngestor()
        self.docx_ingestor = DOCXIngestor()
        self.url_ingestor = URLIngestor()

    async def process_document(self, file_path: str, document_type: str) -> str:
        """Process a document based on its type and return extracted text."""
        try:
            if document_type == "pdf":
                return await self.pdf_ingestor.process_pdf(file_path)
            if document_type in ["txt", "md"]:
                return await self.text_ingestor.process_text(file_path)
            if document_type == "epub":
                return await self.epub_ingestor.process_epub(file_path)
            if document_type == "docx":
                return await self.docx_ingestor.process_docx(file_path)
            msg = f"Unsupported document type: {document_type}"
            raise ValueError(msg)
        except Exception as e:
            msg = f"Failed to process {document_type} document: {e!s}"
            raise ValueError(msg) from e

    # Removed unused process_pdf_document method - use process_document instead

    async def process_url_document(self, url: str) -> tuple[str, datetime]:
        """Process a URL document and return extracted content with crawl date."""
        return await self.url_ingestor.process_url(url)

    def save_file(self, file_content: bytes, filename: str) -> tuple[str, str]:
        """Save file based on type and return path and content hash."""
        file_ext = Path(filename).suffix.lower()

        if file_ext == ".pdf":
            return self.pdf_ingestor.save_file(file_content)
        if file_ext in [".txt", ".md"]:
            return self.text_ingestor.save_file(file_content, filename)
        if file_ext == ".epub":
            return self.epub_ingestor.save_file(file_content, filename)
        if file_ext == ".docx":
            return self.docx_ingestor.save_file(file_content, filename)
        msg = f"Unsupported file type: {file_ext}"
        raise ValueError(msg)

    # Removed unused save_pdf_file method - use save_file instead

async def process_book_rag_background(book_id: UUID) -> None:
    """Process book for RAG in background (non-blocking)."""
    try:
        # Create a new async session for background task
        async with async_session_maker() as session:
            # Update status to processing
            book_query = select(Book).where(Book.id == book_id)
            result = await session.execute(book_query)
            book = result.scalar_one_or_none()

            if not book:
                logger.error(f"Book {book_id} not found for RAG processing")
                return

            book.rag_status = "processing"
            await session.commit()

            # Initialize components
            DocumentProcessor()
            # Use BookChunker for position-aware chunking
            chunker = ChunkerFactory.create_chunker("book")
            vector_store = VectorStore()

            # Process the book file
            file_path = Path(book.file_path)
            if not file_path.exists():
                msg = f"Book file not found: {book.file_path}"
                raise FileNotFoundError(msg)

            # Use enhanced chunking with position data for Phase 5
            enhanced_chunks = chunker.chunk_document(doc_id=book_id, doc_type="book", content=file_path)

            # Store enhanced chunks with embeddings
            # Extract just the content from DocumentChunk objects
            chunk_texts = [chunk.content for chunk in enhanced_chunks]
            await vector_store.store_chunks_with_embeddings(session, book_id, chunk_texts)

            # Update status to completed
            book.rag_status = "completed"
            book.rag_processed_at = datetime.now(UTC)
            await session.commit()

            logger.info(f"Successfully processed book {book_id} for RAG with {len(enhanced_chunks)} chunks")

    except Exception as e:
        logger.exception(f"Failed to process book {book_id} for RAG: {e}")
        # Update status to failed
        try:
            async with async_session_maker() as session:
                book_query = select(Book).where(Book.id == book_id)
                result = await session.execute(book_query)
                book = result.scalar_one_or_none()
                if book:
                    book.rag_status = "failed"
                    await session.commit()
        except Exception as update_error:
            logger.exception(f"Failed to update book {book_id} status to failed: {update_error}")
