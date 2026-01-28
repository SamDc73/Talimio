"""RAG system configuration for LiteLLM + pgvector pipeline."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RAGConfig(BaseSettings):
    """RAG system configuration."""

    # Embedding Configuration
    embedding_model: str = Field(
        default="",  # Optional - RAG might not be configured
        description="Model for generating embeddings via LiteLLM",
    )
    embedding_output_dim: int | None = Field(
        default=None,  # Optional - only needed for models with variable dimensions
        description="Embedding vector dimensions (only for models that support it like OpenAI text-embedding-3)",
    )
    embedding_context_size: int | None = Field(
        default=None,
        description="Optional provider-specific embedding context size",
    )
    embedding_manual_retries: int = Field(
        default=1,
        description="Manual retries for embedding calls (in addition to any provider retries)",
    )
    embedding_retry_delay_seconds: float = Field(
        default=1.0,
        description="Delay in seconds between manual embedding retries",
    )
    embedding_batch_size: int = Field(
        default=1,
        description="Batch size for embedding generation (must be >= 1)",
    )

    # Database Configuration (pgvector)
    hnsw_ef_search: int = Field(
        default=80,
        description="pgvector HNSW query-time ef_search (higher = better recall, slower)",
    )
    hnsw_m: int = Field(
        default=16,
        description="pgvector HNSW graph connectivity (m) used at index build time",
    )
    hnsw_ef_construction: int = Field(
        default=200,
        description="pgvector HNSW ef_construction used at index build time",
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

    # File size limit
    max_file_size_mb: int = Field(
        default=10,  # 10MB default limit
        description="Maximum file size in MB for document processing",
    )

    model_config = SettingsConfigDict(
        env_prefix="RAG_",
        env_file=".env",
        extra="ignore",
    )


# Global configuration instance
rag_config = RAGConfig()
