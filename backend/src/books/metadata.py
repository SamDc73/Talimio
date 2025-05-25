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
        author: str | None = None,
        description: str | None = None,
        language: str | None = None,
        publisher: str | None = None,
        isbn: str | None = None,
        publication_year: int | None = None,
        page_count: int | None = None,
        table_of_contents: list[dict] | None = None,
    ) -> None:
        self.title = title
        self.author = author
        self.description = description
        self.language = language
        self.publisher = publisher
        self.isbn = isbn
        self.publication_year = publication_year
        self.page_count = page_count
        self.table_of_contents = table_of_contents


def extract_pdf_metadata(file_content: bytes) -> BookMetadata:
    """
    Extract metadata from PDF content using PyMuPDF.

    Args:
        file_content: PDF file content as bytes

    Returns
    -------
        BookMetadata object with extracted information
    """
    metadata = BookMetadata()

    try:
        # Open PDF from bytes
        pdf_document = fitz.open(stream=file_content, filetype="pdf")

        # Extract page count
        metadata.page_count = pdf_document.page_count

        # Extract metadata
        pdf_metadata = pdf_document.metadata

        if pdf_metadata:
            # Title
            if pdf_metadata.get("title"):
                metadata.title = pdf_metadata["title"].strip()

            # Author
            if pdf_metadata.get("author"):
                metadata.author = pdf_metadata["author"].strip()
            elif pdf_metadata.get("creator"):
                metadata.author = pdf_metadata["creator"].strip()

            # Description/Subject
            if pdf_metadata.get("subject"):
                metadata.description = pdf_metadata["subject"].strip()

            # Publisher/Producer
            if pdf_metadata.get("producer"):
                metadata.publisher = pdf_metadata["producer"].strip()

            # Creation date - try to extract year
            if pdf_metadata.get("creationDate"):
                try:
                    # PyMuPDF returns dates as strings like "D:20231201120000Z"
                    date_str = pdf_metadata["creationDate"]
                    if date_str.startswith("D:"):
                        year_str = date_str[2:6]
                        metadata.publication_year = int(year_str)
                except (ValueError, IndexError):
                    pass

        # Extract table of contents
        toc = pdf_document.get_toc()
        if toc:
            metadata.table_of_contents = _process_pdf_toc(toc)

        # Close the document
        pdf_document.close()

    except Exception as e:
        logger.warning(f"Failed to extract PDF metadata: {e}")

    return metadata


def extract_epub_metadata(file_content: bytes) -> BookMetadata:
    """
    Extract metadata from EPUB content.

    Args:
        file_content: EPUB file content as bytes

    Returns
    -------
        BookMetadata object with extracted information
    """
    metadata = BookMetadata()

    try:
        # Create a temporary file to work with ebooklib
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name

        try:
            book = epub.read_epub(tmp_path)

            # Title
            title = book.get_metadata("DC", "title")
            if title:
                metadata.title = str(title[0][0]).strip()

            # Author(s)
            creators = book.get_metadata("DC", "creator")
            if creators:
                # Join multiple authors with comma
                authors = [str(creator[0]).strip() for creator in creators]
                metadata.author = ", ".join(authors)

            # Description
            description = book.get_metadata("DC", "description")
            if description:
                metadata.description = str(description[0][0]).strip()

            # Language
            language = book.get_metadata("DC", "language")
            if language:
                metadata.language = str(language[0][0]).strip()

            # Publisher
            publisher = book.get_metadata("DC", "publisher")
            if publisher:
                metadata.publisher = str(publisher[0][0]).strip()

            # ISBN
            identifiers = book.get_metadata("DC", "identifier")
            for identifier in identifiers:
                if identifier[1] and identifier[1].get("id") == "ISBN":
                    metadata.isbn = str(identifier[0]).strip()
                    break

            # Publication date
            date = book.get_metadata("DC", "date")
            if date:
                date_str = str(date[0][0]).strip()
                # Try to extract year from date string
                try:
                    year = int(date_str[:4])
                    metadata.publication_year = year
                except (ValueError, IndexError):
                    pass

            # Page count (approximate from spine items)
            metadata.page_count = len(book.spine)

        finally:
            # Clean up temporary file
            Path(tmp_path).unlink(missing_ok=True)

    except Exception as e:
        logger.warning(f"Failed to extract EPUB metadata: {e}")

    return metadata


def extract_metadata(file_content: bytes, file_extension: str) -> BookMetadata:
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
        return extract_pdf_metadata(file_content)
    if file_extension == ".epub":
        return extract_epub_metadata(file_content)
    logger.warning(f"Unsupported file type for metadata extraction: {file_extension}")
    return BookMetadata()


def _process_pdf_toc(toc: list) -> list[dict]:
    """
    Process PyMuPDF table of contents into a structured format.

    Args:
        toc: PyMuPDF table of contents list

    Returns
    -------
        List of dictionaries representing the table of contents
    """
    result = []
    stack = []  # Stack to track parent chapters

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
