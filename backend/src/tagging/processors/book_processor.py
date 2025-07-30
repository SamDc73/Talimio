"""Book content processor for tag generation."""

import logging
from pathlib import Path

import fitz  # PyMuPDF
from ebooklib import epub

from src.books.models import Book
from src.config.settings import get_settings
from src.database.session import AsyncSession


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
        file_path: str,
    ) -> dict[str, str]:
        """Extract book content for tag generation.

        Args:
            book: Book model instance
            file_path: Path to the book file

        Returns
        -------
            Dictionary with title, author, and content_preview
        """
        try:
            # Read file content
            file_content = Path(file_path).read_bytes()
            file_extension = Path(file_path).suffix.lower()

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
                    toc = pdf_document.get_toc()  # type: ignore[call-non-callable]
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

    def _extract_epub_content(self, file_content: bytes, max_chapters: int = 3) -> str:
        """Extract text from first few chapters of EPUB.

        Args:
            file_content: EPUB file content as bytes
            max_chapters: Maximum number of chapters to extract (default: 3)

        Returns
        -------
            Extracted text content
        """
        content_parts = []

        try:
            # Create a temporary file to work with ebooklib
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp:
                tmp.write(file_content)
                tmp_path = tmp.name

            try:
                book = epub.read_epub(tmp_path)

                # Extract text from first few items
                items_processed = 0

                for item in book.get_items():
                    if items_processed >= max_chapters:
                        break

                    if item.get_type() == 9:  # Document type
                        try:
                            content = item.get_content().decode("utf-8")
                            # Basic HTML stripping (you might want to use BeautifulSoup for better results)
                            import re

                            text = re.sub(r"<[^>]+>", "", content)
                            text = text.strip()

                            if text and len(text) > 100:  # Skip very short sections
                                content_parts.append(text[:2000])  # Limit each section
                                items_processed += 1
                        except Exception as e:
                            logger.debug(f"Failed to extract text from PDF page: {e}")

            finally:
                # Clean up temporary file
                Path(tmp_path).unlink(missing_ok=True)

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
    book_id: str,
    session: AsyncSession,
) -> dict[str, str] | None:
    """Process a book to extract content for tagging.

    Args:
        book_id: ID of the book to process
        session: Database session

    Returns
    -------
        Dictionary with title, author, and content_preview, or None if not found
    """
    from sqlalchemy import select

    # Get book from database
    result = await session.execute(
        select(Book).where(Book.id == book_id),
    )
    book = result.scalar_one_or_none()

    if not book:
        logger.error(f"Book not found: {book_id}")
        return None

    # Construct file path using settings
    settings = get_settings()
    file_path = f"{settings.LOCAL_STORAGE_PATH}/books/{book.file_path}"

    if not Path(file_path).exists():
        logger.error(f"Book file not found: {file_path}")
        # Return basic info from database
        return {
            "title": book.title,
            "author": book.author,
            "content_preview": book.description or "",
        }

    # Process book
    processor = BookProcessor(session)
    return await processor.extract_content_for_tagging(book, file_path)
