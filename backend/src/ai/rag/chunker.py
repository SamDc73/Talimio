"""Simple text chunking using Chonkie."""

from chonkie import SentenceChunker
from fastapi.concurrency import run_in_threadpool


async def chunk_text_async(text: str) -> list[str]:
    """Chunk text using Chonkie's SentenceChunker with default settings."""
    def _chunk_sync(text: str) -> list[str]:
        chunker = SentenceChunker()
        chunks = chunker.chunk(text)
        return [chunk.text for chunk in chunks]

    return await run_in_threadpool(_chunk_sync, text)
