"""Document parsing using Unstructured."""

from fastapi.concurrency import run_in_threadpool

from src.ai.rag.config import rag_config


_DEFAULT_LANGUAGES = ["eng"]


class DocumentProcessor:
    """Document processing using Unstructured partitioning."""

    async def process_document(self, file_path: str, document_type: str) -> str:
        """Extract text from a document on disk."""
        doc_type = (document_type or "").lower()

        if doc_type == "pdf":
            from unstructured.partition.pdf import partition_pdf

            strategy = "hi_res" if rag_config.enable_ocr else "fast"
            elements = await run_in_threadpool(
                partition_pdf,
                filename=file_path,
                strategy=strategy,
                infer_table_structure=rag_config.extract_tables,
                extract_images_in_pdf=rag_config.extract_images,
                ocr_languages="eng" if rag_config.enable_ocr else None,
                languages=_DEFAULT_LANGUAGES,
            )
            return "\n".join(str(el) for el in elements)

        from unstructured.partition.auto import partition

        elements = await run_in_threadpool(
            partition,
            filename=file_path,
            strategy="auto",
            languages=_DEFAULT_LANGUAGES,
        )
        return "\n".join(str(el) for el in elements)
