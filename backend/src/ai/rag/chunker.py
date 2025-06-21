"""Text chunking strategies and implementations."""

from abc import ABC, abstractmethod

from src.ai.constants import rag_config


class BaseChunker(ABC):
    """Abstract base class for text chunking strategies."""

    @abstractmethod
    def chunk_text(self, text: str) -> list[str]:
        """Split text into chunks."""


class BasicChunker(BaseChunker):
    """Simple word-based text chunking with overlap."""

    def __init__(self, chunk_size: int | None = None, chunk_overlap: int | None = None) -> None:
        """Initialize chunker with optional custom sizes."""
        self.chunk_size = chunk_size or rag_config.chunk_size
        self.chunk_overlap = chunk_overlap or rag_config.chunk_overlap
        self.words_per_chunk = int(self.chunk_size * 0.75)  # Rough token estimation
        self.words_overlap = int(self.chunk_overlap * 0.75)

    def chunk_text(self, text: str) -> list[str]:
        """Split text into overlapping word-based chunks."""
        words = text.split()
        chunks = []

        for i in range(0, len(words), self.words_per_chunk - self.words_overlap):
            chunk_words = words[i : i + self.words_per_chunk]
            if chunk_words:
                chunks.append(" ".join(chunk_words))

        return chunks


class LlamaIndexChunker(BaseChunker):
    """Advanced chunking using LlamaIndex (Future Phase 4 implementation)."""

    def __init__(self, chunk_size: int | None = None, chunk_overlap: int | None = None) -> None:
        """Initialize LlamaIndex chunker."""
        self.chunk_size = chunk_size or rag_config.chunk_size
        self.chunk_overlap = chunk_overlap or rag_config.chunk_overlap

    def chunk_text(self, text: str) -> list[str]:
        """Split text using LlamaIndex splitters."""
        # TODO: Implement LlamaIndex chunking in Phase 4
        # For now, fall back to basic chunking
        basic_chunker = BasicChunker(self.chunk_size, self.chunk_overlap)
        return basic_chunker.chunk_text(text)


class ChunkerFactory:
    """Factory class for creating appropriate chunker instances."""

    @staticmethod
    def create_chunker(strategy: str = "basic", **kwargs: int | None) -> BaseChunker:
        """Create a chunker instance based on strategy."""
        if strategy == "basic":
            return BasicChunker(**kwargs)
        if strategy == "llamaindex":
            return LlamaIndexChunker(**kwargs)
        msg = f"Unknown chunking strategy: {strategy}"
        raise ValueError(msg)

    @staticmethod
    def get_default_chunker() -> BaseChunker:
        """Get the default chunker (basic for now)."""
        return BasicChunker()
