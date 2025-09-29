"""Document parsing using Unstructured's auto-partition."""

import logging
from datetime import UTC
from typing import Any

from fastapi.concurrency import run_in_threadpool

from src.ai.rag.config import rag_config


logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Document processing using Unstructured's auto-partition."""

    async def process_document(self, file_path: str, document_type: str) -> str:
        """Process any document using Unstructured's auto-partition."""
        from unstructured.partition.auto import partition

        # Use Unstructured's auto-partition for all file types
        elements = await run_in_threadpool(
            partition,
            filename=file_path,
            strategy="hi_res" if document_type == "pdf" and rag_config.enable_ocr else "auto",
            extract_images_in_pdf=rag_config.extract_images,
            extract_tables=rag_config.extract_tables,
            ocr_languages=["eng"] if rag_config.enable_ocr else None,
        )
        return "\n".join([str(el) for el in elements])

    async def process_url_document(self, url: str) -> tuple[str, Any]:
        """Process a document from URL using Unstructured's auto-partition."""
        from datetime import datetime

        from unstructured.partition.auto import partition

        # Use Unstructured's auto-partition for URL
        elements = await run_in_threadpool(
            partition,
            url=url,
            strategy="auto",
            extract_images_in_pdf=rag_config.extract_images,
            extract_tables=rag_config.extract_tables,
        )

        text_content = "\n".join([str(el) for el in elements])
        crawl_date = datetime.now(UTC)

        return text_content, crawl_date
