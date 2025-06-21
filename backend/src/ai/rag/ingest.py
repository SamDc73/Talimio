"""Document ingestion and processing components."""

import hashlib
import uuid
from datetime import UTC, datetime

import aiohttp
import fitz  # PyMuPDF
from markdownify import markdownify
from readabilipy import simple_json_from_html_string

from src.ai.constants import rag_config


class PDFIngestor:
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
        # Generate unique filename
        file_id = str(uuid.uuid4())
        file_path = rag_config.upload_dir / f"{file_id}.pdf"

        # Save file
        with file_path.open("wb") as f:
            f.write(file_content)

        # Generate content hash for deduplication
        content_hash = hashlib.sha256(file_content).hexdigest()

        return str(file_path), content_hash


class URLIngestor:
    """Extract clean content from web URLs."""

    async def process_url(self, url: str) -> tuple[str, datetime]:
        """Extract clean webpage content as markdown."""
        async with (
            aiohttp.ClientSession() as session,
            session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response,
        ):
            response.raise_for_status()
            content = await response.read()

        # Extract clean content using ReadabiliPy
        article = simple_json_from_html_string(content, use_readability=True)

        # Convert to markdown
        markdown_content = markdownify(article["content"])
        crawl_date = datetime.now(tz=UTC)

        return markdown_content, crawl_date


class DocumentProcessor:
    """Orchestrate document processing pipeline."""

    def __init__(self) -> None:
        """Initialize document processor with ingestors."""
        self.pdf_ingestor = PDFIngestor()
        self.url_ingestor = URLIngestor()

    async def process_pdf_document(self, file_path: str) -> str:
        """Process a PDF document and return extracted text."""
        return await self.pdf_ingestor.process_pdf(file_path)

    async def process_url_document(self, url: str) -> tuple[str, datetime]:
        """Process a URL document and return extracted content with crawl date."""
        return await self.url_ingestor.process_url(url)

    def save_pdf_file(self, file_content: bytes) -> tuple[str, str]:
        """Save PDF file and return path and content hash."""
        return self.pdf_ingestor.save_file(file_content)
