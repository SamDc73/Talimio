"""Document parsing for RAG ingestion."""

from __future__ import annotations

import os
from contextlib import redirect_stderr
from pathlib import Path

import pymupdf
from fastapi.concurrency import run_in_threadpool

from src.ai.rag.exceptions import RagUnavailableError


pymupdf.TOOLS.mupdf_display_errors(on=False)
pymupdf.TOOLS.mupdf_display_warnings(on=False)


_DOCUMENT_FILE_TYPES_BY_EXTENSION = {
    ".pdf": "pdf",
    ".xps": "xps",
    ".oxps": "xps",
    ".epub": "epub",
    ".mobi": "mobi",
    ".fb2": "fb2",
    ".svg": "svg",
    ".txt": "txt",
    ".md": "txt",
    ".markdown": "txt",
}


def _file_type_for_path(file_path: str) -> str:
    """Map supported file extensions to PyMuPDF file types."""
    suffix = Path(file_path).suffix.lower()
    file_type = _DOCUMENT_FILE_TYPES_BY_EXTENSION.get(suffix)
    if file_type is None:
        message = "Unsupported document type for RAG parsing"
        raise RagUnavailableError(message)
    return file_type


def _extract_text_with_pymupdf(file_path: str) -> str:
    """Extract selectable text from a document with PyMuPDF."""
    file_type = _file_type_for_path(file_path)

    try:
        with (
            Path(os.devnull).open("w", encoding="utf-8") as devnull,
            redirect_stderr(devnull),
            pymupdf.open(file_path, filetype=file_type) as document,
        ):
            pages = [page.get_text("text", sort=True).strip() for page in document]
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        message = "RAG document parser failed to read the source file"
        raise RagUnavailableError(message) from error

    return "\n\n".join(page_text for page_text in pages if page_text)


class DocumentProcessor:
    """Document text extraction for supported RAG files."""

    async def process_document(self, file_path: str) -> str:
        """Extract text from a document on disk."""
        return await run_in_threadpool(_extract_text_with_pymupdf, file_path)
