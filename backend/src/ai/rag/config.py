"""Plain RAG configuration derived from canonical application settings."""

from dataclasses import dataclass

from src.config.settings import Settings, get_settings


@dataclass(frozen=True, slots=True)
class RAGConfig:
    """RAG system configuration used by the LiteLLM + pgvector pipeline."""

    embedding_model: str
    embedding_context_size: int | None
    embedding_manual_retries: int
    embedding_retry_delay_seconds: float
    embedding_batch_size: int
    embedding_output_dim: int | None
    hnsw_ef_search: int
    rerank_model: str
    max_file_size_mb: int


def get_rag_config(settings: Settings | None = None) -> RAGConfig:
    """Build RAG configuration from the current application settings."""
    resolved_settings = settings or get_settings()
    return RAGConfig(
        embedding_model=resolved_settings.RAG_EMBEDDING_MODEL,
        embedding_context_size=resolved_settings.RAG_EMBEDDING_CONTEXT_SIZE,
        embedding_manual_retries=resolved_settings.RAG_EMBEDDING_MANUAL_RETRIES,
        embedding_retry_delay_seconds=resolved_settings.RAG_EMBEDDING_RETRY_DELAY_SECONDS,
        embedding_batch_size=resolved_settings.RAG_EMBEDDING_BATCH_SIZE,
        embedding_output_dim=resolved_settings.RAG_EMBEDDING_OUTPUT_DIM,
        hnsw_ef_search=resolved_settings.RAG_HNSW_EF_SEARCH,
        rerank_model=resolved_settings.RAG_RERANK_MODEL,
        max_file_size_mb=resolved_settings.RAG_MAX_FILE_SIZE_MB,
    )
