"""RAG system for per-roadmap document processing and retrieval."""

# Only export what's actually used outside this module
# Other components are imported directly from their submodules when needed

from .chunker import ChunkerFactory
from .ingest import DocumentProcessor
from .retriever import ContextAwareRetriever
from .schemas import SearchResult
from .service import RAGService
from .vector_store import VectorStore


__all__ = [
    "ChunkerFactory",
    "ContextAwareRetriever",
    "DocumentProcessor",
    "RAGService",
    "SearchResult",
    "VectorStore",
]
