"""RAG system for per-roadmap document processing and retrieval."""

# Main service interface
# Modular components (for direct access if needed)
# Database models and schemas
from src.courses.models import DocumentChunk, RoadmapDocument

from .chunker import BasicChunker, ChunkerFactory, LlamaIndexChunker
from .ingest import DocumentProcessor, PDFIngestor, URLIngestor
from .retriever import DocumentRetriever, Reranker
from .schemas import (
    DocumentList,
    DocumentResponse,
    DocumentUpload,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from .vector_store import EmbeddingGenerator, VectorStore


# Public helpers for direct component access
__all__ = [
    "BasicChunker",
    "ChunkerFactory",
    "DocumentChunk",
    "DocumentList",
    "DocumentProcessor",
    "DocumentResponse",
    "DocumentRetriever",
    "DocumentUpload",
    "EmbeddingGenerator",
    "LlamaIndexChunker",
    "PDFIngestor",
    "Reranker",
    "RoadmapDocument",
    "SearchRequest",
    "SearchResponse",
    "SearchResult",
    "URLIngestor",
    "VectorStore",
]
