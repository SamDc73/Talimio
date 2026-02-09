"""Book content processor for tag generation."""

import logging
import os
from contextlib import redirect_stderr
from pathlib import Path
from uuid import UUID

import fitz  # PyMuPDF
from sqlalchemy.ext.asyncio import AsyncSession

from src.books.models import Book
from src.storage.factory import get_storage_provider


logger = logging.getLogger(__name__)


class BookProcessor:
    """Processor for extracting book content for tagging."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize book processor.

        Args:
            session: Database session
        """
        self.session = session

    async def extract_content_for_tagging(
        self,
        book: Book,
        file_content: bytes,
        file_extension: str,
    ) -> dict[str, str]:
        """Extract book content for tag generation.

        Args:
            book: Book model instance
            file_content: File content as bytes
            file_extension: File extension (e.g., ".pdf", ".epub")

        Returns
        -------
            Dictionary with title, author, and content_preview
        """
        try:
            # Extract content based on file type
            if file_extension == ".pdf":
                content_preview = self._extract_pdf_content(file_content)
            elif file_extension == ".epub":
                content_preview = self._extract_epub_content(file_content)
            else:
                logger.warning(f"Unsupported file type for content extraction: {file_extension}")
                content_preview = ""

            # Combine metadata for better tagging
            combined_preview = self._build_content_preview(
                book=book,
                extracted_content=content_preview,
            )

            return {
                "title": f"{book.title} {book.subtitle or ''}".strip(),
                "author": book.author,
                "content_preview": combined_preview,
            }

        except Exception as e:
            logger.exception(f"Error extracting book content for tagging: {e}")
            return {
                "title": book.title,
                "author": book.author,
                "content_preview": book.description or "",
            }

    def _extract_pdf_content(self, file_content: bytes, max_pages: int = 5) -> str:
        """Extract text from first few pages of PDF.

        Args:
            file_content: PDF file content as bytes
            max_pages: Maximum number of pages to extract (default: 5)

        Returns
        -------
            Extracted text content
        """
        content_parts = []

        try:
            # Open PDF from bytes
            pdf_document = fitz.open(stream=file_content, filetype="pdf")

            if pdf_document is None:
                logger.warning("Failed to open PDF document")
                return "\n\n".join(content_parts)

            # Extract text from first few pages
            pages_to_read = min(max_pages, pdf_document.page_count)

            for page_num in range(pages_to_read):
                page = pdf_document[page_num]
                text = page.get_text()

                # Clean up text
                text = text.strip()
                if text:
                    content_parts.append(text)

            # Try to extract table of contents for better context
            try:
                if hasattr(pdf_document, "get_toc"):
                    toc = pdf_document.get_toc()
                    if toc:
                        toc_text = self._format_toc_for_tagging(toc)
                        if toc_text:
                            content_parts.insert(0, f"Table of Contents:\n{toc_text}\n")
            except (AttributeError, Exception):
                # get_toc() method might not be available in some versions
                logger.debug("get_toc() method not available for this PDF")

            pdf_document.close()

        except Exception as e:
            logger.warning(f"Failed to extract PDF content: {e}")

        return "\n\n".join(content_parts)

    def _extract_epub_content(self, file_content: bytes, max_pages: int = 10) -> str:
        """Extract text from first few pages of EPUB.

        Args:
            file_content: EPUB file content as bytes
            max_pages: Maximum number of pages to extract (default: 10)

        Returns
        -------
            Extracted text content
        """
        content_parts = []

        try:
            # Open EPUB directly from bytes with PyMuPDF (suppress MuPDF CSS warnings)
            with redirect_stderr(Path(os.devnull).open("w")):
                epub_document = fitz.open(stream=file_content, filetype="epub")

            if epub_document is None:
                logger.warning("Failed to open EPUB document")
                return "\n\n".join(content_parts)

            # Extract metadata
            metadata = epub_document.metadata
            if metadata:
                if metadata.get("title"):
                    content_parts.append(f"Title: {metadata['title']}")
                if metadata.get("author"):
                    content_parts.append(f"Author: {metadata['author']}")

            # Extract text from first few pages
            pages_to_read = min(max_pages, epub_document.page_count)

            for page_num in range(pages_to_read):
                page = epub_document[page_num]
                page_text = page.get_text().strip()
                if page_text:
                    # Limit text per page for tagging
                    content_parts.append(page_text[:2000])

            epub_document.close()

        except Exception as e:
            logger.warning(f"Failed to extract EPUB content: {e}")

        return "\n\n".join(content_parts)

    def _format_toc_for_tagging(self, toc: list) -> str:
        """Format table of contents for tag generation.

        Args:
            toc: PyMuPDF table of contents

        Returns
        -------
            Formatted TOC string
        """
        toc_lines = []

        for entry in toc[:20]:  # Limit to first 20 entries
            level, title, _ = entry
            indent = "  " * (level - 1)
            toc_lines.append(f"{indent}{title}")

        return "\n".join(toc_lines)

    def _build_content_preview(
        self,
        book: Book,
        extracted_content: str,
        max_length: int = 3000,
    ) -> str:
        """Build comprehensive content preview for tagging.

        Args:
            book: Book model instance
            extracted_content: Extracted text content
            max_length: Maximum preview length

        Returns
        -------
            Combined content preview
        """
        parts = []

        # Add book metadata
        if book.description:
            parts.append(f"Description: {book.description}")

        if book.publisher:
            parts.append(f"Publisher: {book.publisher}")

        if book.tags:
            # Include existing tags if any
            import json

            try:
                existing_tags = json.loads(book.tags)
                if existing_tags:
                    parts.append(f"Existing tags: {', '.join(existing_tags)}")
            except Exception as e:
                logger.debug(f"Failed to parse existing tags: {e}")

        # Add extracted content
        if extracted_content:
            parts.append("Content Preview:")
            parts.append(extracted_content)

        # Combine and truncate
        preview = "\n\n".join(parts)

        if len(preview) > max_length:
            preview = preview[:max_length] + "..."

        return preview


async def process_book_for_tagging(
    book_id: UUID,
    user_id: UUID,
    session: AsyncSession,
) -> dict[str, str] | None:
    """Process a book to extract content for tagging.

    Args:
        book_id: ID of the book to process
        user_id: Owner user ID
        session: Database session

    Returns
    -------
        Dictionary with title, author, and content_preview, or None if not found
    """
    from sqlalchemy import select

    # Get book from database
    result = await session.execute(
        select(Book).where(Book.id == book_id, Book.user_id == user_id),
    )
    book = result.scalar_one_or_none()

    if not book:
        logger.error(f"Book not found: {book_id}")
        return None

    try:
        # Get storage provider and download file content
        storage = get_storage_provider()
        file_content = await storage.download(book.file_path)

        # Determine file extension from file path
        file_extension = f".{book.file_type}" if book.file_type else ".pdf"

        # Process book
        processor = BookProcessor(session)
        return await processor.extract_content_for_tagging(book, file_content, file_extension)

    except Exception as e:
        logger.exception(f"Error downloading or processing book file: {e}")
        # Return basic info from database as fallback
        return {
            "title": book.title,
            "author": book.author,
            "content_preview": book.description or "",
        }
