"""RAG system configuration using txtai."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class RAGConfig(BaseSettings):
    """RAG system configuration."""

    # txtai Configuration
    embedding_model: str = Field(
        default="",  # Optional - RAG might not be configured
        description="Model for generating embeddings via txtai",
    )
    embedding_output_dim: int | None = Field(
        default=None,  # Optional - only needed for models with variable dimensions
        description="Embedding vector dimensions (only for models that support it like OpenAI text-embedding-3)",
    )

    # Database Configuration (pgvector)
    vector_index_method: Literal["ivfflat", "hnsw"] = Field(
        default="hnsw",
        description="Vector index method for pgvector",
    )
    vector_index_lists: int = Field(
        default=100,
        description="Number of lists for IVFFlat index",
    )

    # Chunking Configuration (Chonkie)
    chunking_strategy: Literal["semantic", "sentence", "token", "hybrid"] = Field(
        default="semantic",
        description="Chunking strategy for documents",
    )

    # Parsing Configuration (Unstructured)
    enable_ocr: bool = Field(
        default=False,  # Disabled to avoid tesseract dependency
        description="Enable OCR for scanned PDFs",
    )
    extract_tables: bool = Field(
        default=True,
        description="Extract tables from documents",
    )
    extract_images: bool = Field(
        default=False,
        description="Extract and process images from documents",
    )

    # Search Configuration
    top_k: int = Field(
        default=50,  # Match the value from .env
        description="Number of chunks to retrieve before reranking",
    )
    rerank_k: int = Field(
        default=10,  # Sensible default
        description="Number of chunks to return after reranking",
    )
    rerank_model: str = Field(
        default="",  # Optional - reranking might not be configured
        description="Model for reranking results",
    )
    rerank_enabled: bool = Field(
        default=False,  # Disabled by default if not configured
        description="Whether to enable reranking",
    )
    min_similarity_score: float = Field(
        default=0.5,
        description="Minimum similarity score for results",
    )

    # Memory Configuration (Mem0)
    enable_memory: bool = Field(
        default=True,
        description="Enable memory layer for context",
    )
    memory_window_size: int = Field(
        default=10,
        description="Number of recent interactions to remember",
    )

    # Temporary Processing Configuration
    # NOTE: This is separate from the main storage system (/src/storage/)
    # RAG uses temporary local files during document processing (parsing, chunking)
    # which are cleaned up after chunks are stored in the database.
    # Main storage handles permanent user files (books, uploads).
    temp_processing_dir: Path = Field(
        default=Path("temp/rag_processing"),
        description="Temporary directory for document processing (cleaned after processing)",
    )
    max_file_size_mb: int = Field(
        default=10,  # 10MB default limit
        description="Maximum file size in MB",
    )

    # Processing Configuration
    batch_size: int = Field(
        default=10,
        description="Batch size for processing documents",
    )
    max_workers: int = Field(
        default=4,
        description="Maximum number of parallel workers",
    )

    class Config:
        """Pydantic configuration."""

        env_prefix = "RAG_"
        env_file = ".env"
        extra = "ignore"


# Global configuration instance
rag_config = RAGConfig()


# Supported file types and their configurations (MVP: only essential formats)
SUPPORTED_FILE_TYPES = {
    ".pdf": {
        "mime_types": ["application/pdf"],
        "parser": "pdf",
        "chunker": "semantic",
    },
    ".txt": {
        "mime_types": ["text/plain"],
        "parser": "text",
        "chunker": "sentence",
    },
    ".md": {
        "mime_types": ["text/markdown", "text/x-markdown"],
        "parser": "markdown",
        "chunker": "semantic",
    },
    ".epub": {
        "mime_types": ["application/epub+zip"],
        "parser": "epub",
        "chunker": "semantic",
    },
}


def get_parser_for_file(filename: str) -> str:
    """Get the appropriate parser for a file type."""
    suffix = Path(filename).suffix.lower()
    config = SUPPORTED_FILE_TYPES.get(suffix, {})
    return config.get("parser", "text")


def get_chunker_for_file(filename: str) -> str:
    """Get the appropriate chunker for a file type."""
    suffix = Path(filename).suffix.lower()
    config = SUPPORTED_FILE_TYPES.get(suffix, {})
    return config.get("chunker", "semantic")
