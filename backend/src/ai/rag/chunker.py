"""Text chunking strategies using the Chonkie library (defaults only)."""

from chonkie import SentenceChunker as ChonkieSentenceChunker
from fastapi.concurrency import run_in_threadpool


class SemanticChunker:
    """Semantic text chunking using Chonkie."""

    def __init__(self, _chunk_size: int = 2048, _chunk_overlap: int = 128) -> None:
        """Initialize semantic chunker with Chonkie defaults (signature kept for compatibility)."""
        # Use Chonkie's default SentenceChunker configuration and defaults
        self._chunker = ChonkieSentenceChunker()

    def chunk_text(self, text: str) -> list[str]:
        """Split text into chunks using Chonkie with default settings."""
        # Delegate to Chonkie and return only raw text for each chunk
        chunks = self._chunker.chunk(text)
        return [c.text for c in chunks]

    async def chunk_text_async(self, text: str) -> list[str]:
        """Async version of chunk_text for thread pool execution."""
        return await run_in_threadpool(self.chunk_text, text)
class ChunkerFactory:
    """Factory class for creating appropriate chunker instances."""

    @staticmethod
    def get_default_chunker() -> "SemanticChunker":
        """Get the default chunker (semantic)."""
        return SemanticChunker()
