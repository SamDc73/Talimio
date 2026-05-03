"""Text chunking helpers using Chonkie."""

from __future__ import annotations

import re

from chonkie import Chunk, RecursiveChunker, RecursiveLevel, RecursiveRules
from chonkie.refinery import OverlapRefinery
from fastapi.concurrency import run_in_threadpool

from src.ai.rag.exceptions import RagUnavailableError


_CHUNK_SIZE = 1_600
_CHUNK_OVERLAP_RATIO = 0.12
_MIN_CHARS_PER_CHUNK = 120
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def _build_markdown_rules() -> RecursiveRules:
    """Build local Markdown-aware rules without loading remote recipes."""
    return RecursiveRules(
        levels=[
            RecursiveLevel(delimiters=["\n# ", "\n## ", "\n### ", "\n#### "], include_delim="next"),
            RecursiveLevel(delimiters=["\n\n", "\r\n\r\n", "\n", "\r"], include_delim="prev"),
            RecursiveLevel(delimiters=[". ", "! ", "? "], include_delim="prev"),
            RecursiveLevel(whitespace=True),
            RecursiveLevel(),
        ]
    )


def _collect_heading_context(text: str) -> list[tuple[int, str, str]]:
    """Collect heading offsets and section paths from Markdown-ish text."""
    headings: list[tuple[int, str, str]] = []
    stack: dict[int, str] = {}

    for match in _HEADING_RE.finditer(text):
        level = len(match.group(1))
        title = match.group(2).strip()
        for existing_level in list(stack):
            if existing_level >= level:
                del stack[existing_level]
        stack[level] = title
        section_path = " > ".join(stack[key] for key in sorted(stack))
        headings.append((match.start(), title, section_path))

    return headings


def _metadata_for_chunk(start_index: int, headings: list[tuple[int, str, str]]) -> dict[str, object]:
    """Return source-section metadata for a chunk offset."""
    metadata: dict[str, object] = {}
    for heading_start, section_title, section_path in headings:
        if heading_start > start_index:
            break
        metadata["section_title"] = section_title
        metadata["section_path"] = section_path
    return metadata


def _is_useful_chunk(text: str) -> bool:
    """Skip tiny heading-only chunks that add noise to retrieval."""
    body = _HEADING_RE.sub("", text).strip()
    return len(body) >= _MIN_CHARS_PER_CHUNK


def _add_chunk_context(text: str, document_title: str | None, metadata: dict[str, object]) -> str:
    """Prepend source context so embedded chunks carry their book location."""
    context_lines: list[str] = []
    if document_title:
        context_lines.append(f"Source: {document_title}")
    section_path = metadata.get("section_path")
    if isinstance(section_path, str) and section_path:
        context_lines.append(f"Section: {section_path}")

    if not context_lines:
        return text.strip()
    context = "\n".join(context_lines)
    return f"{context}\n\n{text.strip()}"


def _chunk_text_with_metadata_sync(text: str, document_title: str | None) -> tuple[list[str], list[dict[str, object]]]:
    """Chunk text and keep source-section metadata beside each chunk."""
    normalized_text = text.strip()
    if not normalized_text:
        return [], []

    heading_context = _collect_heading_context(normalized_text)
    chunker = RecursiveChunker(
        tokenizer="character",
        chunk_size=_CHUNK_SIZE,
        rules=_build_markdown_rules(),
        min_characters_per_chunk=_MIN_CHARS_PER_CHUNK,
    )
    raw_chunks = []
    for chunk in chunker.chunk(normalized_text):
        if not _is_useful_chunk(chunk.text):
            continue
        chunk.metadata.update(_metadata_for_chunk(chunk.start_index, heading_context))
        chunk.metadata["contextualized"] = True
        raw_chunks.append(chunk)

    if not raw_chunks:
        return [], []

    overlap_refinery = OverlapRefinery(
        tokenizer="character",
        context_size=_CHUNK_OVERLAP_RATIO,
        method="prefix",
        merge=False,
    )
    refined_chunks: list[Chunk] = overlap_refinery.refine(raw_chunks)

    chunks: list[str] = []
    metadata: list[dict[str, object]] = []
    for chunk in refined_chunks:
        chunk_text = chunk.text.strip()
        chunk_metadata = dict(chunk.metadata)
        chunks.append(_add_chunk_context(chunk_text, document_title, chunk_metadata))
        metadata.append(chunk_metadata)

    return chunks, metadata


async def chunk_text_with_metadata_async(
    text: str,
    *,
    document_title: str | None = None,
) -> tuple[list[str], list[dict[str, object]]]:
    """Chunk text and return metadata aligned by chunk index."""
    try:
        return await run_in_threadpool(_chunk_text_with_metadata_sync, text, document_title)
    except OSError as error:
        message = "RAG text chunking failed"
        raise RagUnavailableError(message) from error
