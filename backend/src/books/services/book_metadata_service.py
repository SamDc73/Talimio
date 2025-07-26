
"""Book metadata extraction utilities."""

import logging
from pathlib import Path

import fitz  # PyMuPDF
from ebooklib import epub


logger = logging.getLogger(__name__)


class BookMetadata:
    """Container for extracted book metadata."""

    def __init__(
        self,
        title: str | None = None,
        subtitle: str | None = None,
        author: str | None = None,
        description: str | None = None,
        language: str | None = None,
        publisher: str | None = None,
        isbn: str | None = None,
        publication_year: int | None = None,
        page_count: int | None = None,
        table_of_contents: list[dict] | None = None,
        file_type: str | None = None,
    ) -> None:
        self.title = title
        self.subtitle = subtitle
        self.author = author
        self.description = description
        self.language = language
        self.publisher = publisher
        self.isbn = isbn
        self.publication_year = publication_year
        self.page_count = page_count
        self.total_pages = page_count  # Alias for compatibility
        self.table_of_contents = table_of_contents
        self.file_type = file_type


class BookMetadataService:
    """Service for extracting metadata from book files."""

    def extract_metadata(self, file_content: bytes, file_extension: str) -> BookMetadata:
        """
        Extract metadata from book file content.

        Args:
            file_content: File content as bytes
            file_extension: File extension (e.g., ".pdf", ".epub")

        Returns
        -------
            BookMetadata object with extracted information
        """
        file_extension = file_extension.lower()

        if file_extension == ".pdf":
            return self._extract_pdf_metadata(file_content)
        if file_extension == ".epub":
            return self._extract_epub_metadata(file_content)
        logger.warning(f"Unsupported file type for metadata extraction: {file_extension}")
        return BookMetadata()

    def _extract_pdf_metadata(self, file_content: bytes) -> BookMetadata:
        """
        Extract metadata from PDF content using PyMuPDF.

        Args:
            file_content: PDF file content as bytes

        Returns
        -------
            BookMetadata object with extracted information
        """
        metadata = BookMetadata()
        metadata.file_type = "pdf"

        try:
            pdf_document = fitz.open(stream=file_content, filetype="pdf")
            metadata.page_count = pdf_document.page_count
            metadata.total_pages = pdf_document.page_count

            pdf_metadata = pdf_document.metadata
            if pdf_metadata:
                self._extract_pdf_basic_fields(metadata, pdf_metadata)
                self._extract_pdf_publication_year(metadata, pdf_metadata)

            toc = pdf_document.get_toc()
            if toc:
                metadata.table_of_contents = self._process_pdf_toc(toc)

            pdf_document.close()

        except Exception as e:
            logger.warning(f"Failed to extract PDF metadata: {e}")

        return metadata

    def _extract_epub_metadata(self, file_content: bytes) -> BookMetadata:
        """
        Extract metadata from EPUB content.

        Args:
            file_content: EPUB file content as bytes

        Returns
        -------
            BookMetadata object with extracted information
        """
        metadata = BookMetadata()
        metadata.file_type = "epub"

        try:
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp:
                tmp.write(file_content)
                tmp_path = tmp.name

            try:
                book = epub.read_epub(tmp_path)
                self._extract_epub_basic_fields(metadata, book)
                self._extract_epub_identifiers(metadata, book)
                self._extract_epub_publication_date(metadata, book)
                metadata.page_count = len(book.spine)
                metadata.total_pages = len(book.spine)

            finally:
                Path(tmp_path).unlink(missing_ok=True)

        except Exception as e:
            logger.warning(f"Failed to extract EPUB metadata: {e}")

        return metadata

    def _extract_epub_basic_fields(self, metadata: BookMetadata, book: epub.EpubBook) -> None:
        """Extract basic metadata fields from EPUB."""
        title = book.get_metadata("DC", "title")
        if title:
            metadata.title = str(title[0][0]).strip()

        creators = book.get_metadata("DC", "creator")
        if creators:
            authors = [str(creator[0]).strip() for creator in creators]
            metadata.author = ", ".join(authors)

        description = book.get_metadata("DC", "description")
        if description:
            metadata.description = str(description[0][0]).strip()

        language = book.get_metadata("DC", "language")
        if language:
            metadata.language = str(language[0][0]).strip()

        publisher = book.get_metadata("DC", "publisher")
        if publisher:
            metadata.publisher = str(publisher[0][0]).strip()

    def _extract_epub_identifiers(self, metadata: BookMetadata, book: epub.EpubBook) -> None:
        """Extract ISBN from EPUB identifiers."""
        identifiers = book.get_metadata("DC", "identifier")
        for identifier in identifiers:
            if identifier[1] and identifier[1].get("id") == "ISBN":
                metadata.isbn = str(identifier[0]).strip()
                break

    def _extract_epub_publication_date(self, metadata: BookMetadata, book: epub.EpubBook) -> None:
        """Extract publication year from EPUB date metadata."""
        date = book.get_metadata("DC", "date")
        if not date:
            return

        try:
            date_str = str(date[0][0]).strip()
            year = int(date_str[:4])
            metadata.publication_year = year
        except (ValueError, IndexError):
            pass

    def _extract_pdf_basic_fields(self, metadata: BookMetadata, pdf_metadata: dict) -> None:
        """Extract basic fields from PDF metadata."""
        if pdf_metadata.get("title"):
            metadata.title = pdf_metadata["title"].strip()

        if pdf_metadata.get("author"):
            metadata.author = pdf_metadata["author"].strip()
        elif pdf_metadata.get("creator"):
            metadata.author = pdf_metadata["creator"].strip()

        if pdf_metadata.get("subject"):
            metadata.description = pdf_metadata["subject"].strip()

        if pdf_metadata.get("producer"):
            metadata.publisher = pdf_metadata["producer"].strip()

    def _extract_pdf_publication_year(self, metadata: BookMetadata, pdf_metadata: dict) -> None:
        """Extract publication year from PDF metadata."""
        if not pdf_metadata.get("creationDate"):
            return

        try:
            date_str = pdf_metadata["creationDate"]
            if date_str.startswith("D:"):
                year_str = date_str[2:6]
                metadata.publication_year = int(year_str)
        except (ValueError, IndexError):
            pass

    def _process_pdf_toc(self, toc: list) -> list[dict]:
        """
        Process PyMuPDF table of contents into a structured format.

        Args:
            toc: PyMuPDF table of contents list

        Returns
        -------
            List of dictionaries representing the table of contents
        """
        result: list[dict] = []
        stack: list[dict] = []  # Stack to track parent chapters

        for entry in toc:
            level, title, page = entry

            # Create TOC item
            item = {
                "id": f"toc_{len(result)}_{level}_{page}",
                "title": title.strip(),
                "page": page,
                "level": level - 1,  # Make it 0-based
                "children": [],
            }

            # Handle hierarchy
            while stack and stack[-1]["level"] >= item["level"]:
                stack.pop()

            if stack:
                # Add as child to parent
                stack[-1]["children"].append(item)
            else:
                # Top-level item
                result.append(item)

            # Add to stack for potential children
            stack.append(item)

        return result
