"""Book metadata extraction utilities."""

import json
import logging

import fitz  # PyMuPDF


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
        total_pages: int | None = None,
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
        self.total_pages = total_pages
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
            metadata.total_pages = pdf_document.page_count

            pdf_metadata = pdf_document.metadata
            if pdf_metadata:
                self._extract_document_basic_fields(metadata, pdf_metadata)
                self._extract_document_publication_year(metadata, pdf_metadata)

            # Extract table of contents
            try:
                toc = pdf_document.get_toc()  # type: ignore[attr-defined]
                if toc:
                    metadata.table_of_contents = self._process_toc(toc)
            except AttributeError:
                logger.debug("PDF document does not support get_toc method")

            pdf_document.close()

        except Exception as e:
            logger.warning(f"Failed to extract PDF metadata: {e}")

        return metadata

    def _extract_epub_metadata(self, file_content: bytes) -> BookMetadata:
        """
        Extract metadata from EPUB content using PyMuPDF.

        Args:
            file_content: EPUB file content as bytes

        Returns
        -------
            BookMetadata object with extracted information
        """
        metadata = BookMetadata()
        metadata.file_type = "epub"

        try:
            # Open EPUB with PyMuPDF
            epub_document = fitz.open(stream=file_content, filetype="epub")

            # Get page count (EPUBs in PyMuPDF are treated as pages)
            metadata.total_pages = epub_document.page_count

            # Extract metadata (similar to PDF)
            epub_metadata = epub_document.metadata
            if epub_metadata:
                self._extract_document_basic_fields(metadata, epub_metadata)
                self._extract_document_publication_year(metadata, epub_metadata)

            # Extract table of contents - this works for EPUB too!
            try:
                toc = epub_document.get_toc()  # type: ignore[attr-defined]
                if toc:
                    metadata.table_of_contents = self._process_toc(toc)
            except AttributeError:
                logger.debug("EPUB document does not support get_toc method")

            epub_document.close()

        except Exception as e:
            logger.warning(f"Failed to extract EPUB metadata: {e}")

        return metadata

    def _extract_document_basic_fields(self, metadata: BookMetadata, doc_metadata: dict) -> None:
        """Extract basic fields from document metadata (works for both PDF and EPUB)."""
        if doc_metadata.get("title"):
            metadata.title = doc_metadata["title"].strip()

        if doc_metadata.get("author"):
            metadata.author = doc_metadata["author"].strip()
        elif doc_metadata.get("creator"):
            metadata.author = doc_metadata["creator"].strip()

        if doc_metadata.get("subject"):
            metadata.description = doc_metadata["subject"].strip()

        # Note: "producer" is the PDF creation software, NOT the book publisher
        # Publisher info is not available in standard PDF metadata
        # We should NOT use producer as publisher - it's misleading

    def _extract_document_publication_year(self, metadata: BookMetadata, doc_metadata: dict) -> None:
        """Extract publication year from document metadata (works for both PDF and EPUB)."""
        if not doc_metadata.get("creationDate"):
            return

        try:
            date_str = doc_metadata["creationDate"]
            if date_str.startswith("D:"):
                year_str = date_str[2:6]
                metadata.publication_year = int(year_str)
        except (ValueError, IndexError):
            pass

    def _process_toc(self, toc: list) -> list[dict]:
        """
        Process PyMuPDF table of contents into a structured format; works for both PDF and EPUB documents.

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

    @staticmethod
    def serialize_toc_for_db(table_of_contents: list[dict] | None) -> str | None:
        """
        Serialize table of contents for database storage.

        Args:
            table_of_contents: TOC list from extraction

        Returns
        -------
            JSON string for database storage or None
        """
        if table_of_contents:
            return json.dumps(table_of_contents)
        return None

    @staticmethod
    def deserialize_toc_from_db(toc_json: str | None) -> list[dict] | None:
        """
        Deserialize table of contents from database.

        Args:
            toc_json: JSON string from database

        Returns
        -------
            TOC list or None
        """
        if not toc_json:
            return None

        try:
            toc_data = json.loads(toc_json)
            if isinstance(toc_data, list):
                return toc_data
        except (json.JSONDecodeError, TypeError):
            logger.warning("Failed to deserialize TOC from database")

        return None

    @staticmethod
    def convert_toc_to_schema(toc_data: list[dict]) -> list:
        """
        Convert table of contents data to schema objects.

        Note: Returns list of dicts for now to avoid circular imports.
        The schema conversion should be done at the API layer.

        Args:
            toc_data: List of TOC dictionaries

        Returns
        -------
            List of processed TOC items with children
        """
        result = []
        for item in toc_data:
            children = []
            if item.get("children"):
                children = BookMetadataService.convert_toc_to_schema(item["children"])

            toc_item = {
                "id": item.get("id", ""),
                "title": item.get("title", ""),
                "page": item.get("page", 1),
                "children": children,
                "level": item.get("level", 0),
            }
            result.append(toc_item)
        return result
