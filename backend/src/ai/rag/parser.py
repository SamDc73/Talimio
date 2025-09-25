"""Document parsing using Unstructured library."""

import hashlib
import logging
import uuid
from pathlib import Path
from typing import Any

import fitz
from fastapi.concurrency import run_in_threadpool

from src.ai.rag.config import rag_config


logger = logging.getLogger(__name__)


class BaseIngestor:
    """Base class for document ingestors with common functionality."""

    def save_file_base(self, file_content: bytes, extension: str) -> tuple[str, str]:
        """Save binary file with given extension and return path and content hash."""
        # Generate unique filename
        file_id = str(uuid.uuid4())
        file_path = rag_config.temp_processing_dir / f"{file_id}.{extension}"

        # Save file
        with file_path.open("wb") as f:
            f.write(file_content)

        # Generate content hash for deduplication
        content_hash = hashlib.sha256(file_content).hexdigest()

        return str(file_path), content_hash


class PDFIngestor(BaseIngestor):
    """Extract text from PDF documents using Unstructured."""

    async def process_pdf(self, file_path: str) -> str:
        """Extract text from PDF with advanced features using Unstructured."""
        try:
            from unstructured.partition.pdf import partition_pdf

            # Run Unstructured in thread pool for async compatibility
            elements = await run_in_threadpool(
                partition_pdf,
                filename=file_path,
                strategy="hi_res" if rag_config.enable_ocr else "fast",
                extract_images_in_pdf=rag_config.extract_images,
                extract_tables=rag_config.extract_tables,
                infer_table_structure=rag_config.extract_tables,
                # TODO: Future enhancement - add language detection or per-document config
                # For now, default to English which covers most use cases
                ocr_languages=["eng"] if rag_config.enable_ocr else None,
            )
            return "\n".join([str(el) for el in elements])

        except ImportError:
            # Fallback to PyMuPDF if Unstructured not available
            logger.warning("Unstructured not available, falling back to PyMuPDF")
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
        """Extract text from text/markdown files using Unstructured."""
        try:
            from unstructured.partition.md import partition_md
            from unstructured.partition.text import partition_text

            # Use appropriate parser based on file extension
            if file_path.lower().endswith(".md"):
                elements = await run_in_threadpool(partition_md, filename=file_path)
            else:
                elements = await run_in_threadpool(partition_text, filename=file_path)

            return "\n".join([str(el) for el in elements])

        except ImportError:
            # Fallback to simple text reading
            logger.warning("Unstructured not available, using simple text reading")
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
        file_path = rag_config.temp_processing_dir / f"{file_id}{original_ext}"

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
        """Extract text from EPUB using Unstructured."""
        try:
            from unstructured.partition.epub import partition_epub

            # Run Unstructured in thread pool for async compatibility
            elements = await run_in_threadpool(partition_epub, filename=file_path)
            return "\n".join([str(el) for el in elements])

        except ImportError:
            # Fallback to PyMuPDF if Unstructured not available
            logger.warning("Unstructured EPUB support not available, falling back to PyMuPDF")
            try:
                doc = fitz.open(file_path)
                text_content = ""

                # Extract metadata if available
                metadata = doc.metadata
                if metadata:
                    if metadata.get("title"):
                        text_content += f"Title: {metadata['title']}\n\n"
                    if metadata.get("author"):
                        text_content += f"Author: {metadata['author']}\n\n"

                # Extract text from all pages
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    page_text = page.get_text().strip()
                    if page_text:
                        text_content += page_text + "\n\n"

                doc.close()
                return text_content
            except Exception as e:
                msg = f"Failed to process EPUB file: {e!s}"
                raise ValueError(msg) from e

    def save_file(self, file_content: bytes, _filename: str) -> tuple[str, str]:
        """Save EPUB file to disk and return path and content hash."""
        return self.save_file_base(file_content, "epub")

class DocumentProcessor:
    """Orchestrate document processing with Unstructured."""

    def __init__(self) -> None:
        """Initialize document processor with supported ingestors."""
        self.pdf_ingestor = PDFIngestor()
        self.text_ingestor = TextIngestor()
        self.epub_ingestor = EPUBIngestor()

        # Unstructured partition factory initialized on demand

    async def process_document(self, file_path: str, document_type: str) -> str:
        """Process a document using Unstructured's auto-partition."""
        try:
            from unstructured.partition.auto import partition

            # Use Unstructured's auto-partition for intelligent file handling
            elements = await run_in_threadpool(
                partition,
                filename=file_path,
                strategy="hi_res" if document_type == "pdf" and rag_config.enable_ocr else "auto",
                extract_images_in_pdf=rag_config.extract_images,
                extract_tables=rag_config.extract_tables,
                # TODO: Future enhancement - add language detection or per-document config
                # For now, default to English which covers most use cases
                ocr_languages=["eng"] if rag_config.enable_ocr else None,
            )
            return "\n".join([str(el) for el in elements])

        except ImportError:
            # Fallback to specific processors
            logger.warning("Unstructured auto-partition not available, using specific processors")

        # Supported types only: pdf, epub, txt, md
        try:
            if document_type == "pdf":
                return await self.pdf_ingestor.process_pdf(file_path)
            if document_type in ["txt", "md"]:
                return await self.text_ingestor.process_text(file_path)
            if document_type == "epub":
                return await self.epub_ingestor.process_epub(file_path)

            msg = f"Unsupported document type: {document_type}. Only pdf, epub, txt, md are supported."
            raise ValueError(msg)
        except Exception as e:
            msg = f"Failed to process {document_type} document: {e!s}"
            raise ValueError(msg) from e

    async def extract_structured_data(self, _file_path: str) -> dict[str, Any]:
        """Extract structured data (tables, images, metadata) from document."""
        # Structured extraction with Unstructured not yet implemented
        return {"tables": [], "images": [], "metadata": {}}

    def save_file(self, file_content: bytes, filename: str) -> tuple[str, str]:
        """Save file based on type and return path and content hash."""
        file_ext = Path(filename).suffix.lower()

        if file_ext == ".pdf":
            return self.pdf_ingestor.save_file(file_content)
        if file_ext in [".txt", ".md"]:
            return self.text_ingestor.save_file(file_content, filename)
        if file_ext == ".epub":
            return self.epub_ingestor.save_file(file_content, filename)

        msg = f"Unsupported file type: {file_ext}. Only .pdf, .epub, .txt, .md are supported."
        raise ValueError(msg)

    # Note: save_file methods remain for backward compatibility
    # Future: Move file saving to a separate FileManager class
