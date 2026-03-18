"""Document parsing using Unstructured."""

from fastapi.concurrency import run_in_threadpool
from pypdf import PdfReader


_DEFAULT_LANGUAGES = ["eng"]


def _extract_text_from_pdf(file_path: str) -> str:
    """Extract plain text from a PDF using pypdf."""
    reader = PdfReader(file_path, strict=False)
    chunks: list[str] = []

    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            chunks.append(page_text)

    return "\n".join(chunks)


class DocumentProcessor:
    """Document processing using Unstructured partitioning."""

    async def process_document(self, file_path: str, document_type: str) -> str:
        """Extract text from a document on disk."""
        doc_type = (document_type or "").lower()

        if doc_type == "pdf":
            return await run_in_threadpool(_extract_text_from_pdf, file_path)

        from unstructured.partition.auto import partition

        elements = await run_in_threadpool(
            partition,
            filename=file_path,
            strategy="auto",
            languages=_DEFAULT_LANGUAGES,
        )
        return "\n".join(str(el) for el in elements)
