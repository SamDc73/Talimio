"""Constants for AI module configuration."""

import os
from pathlib import Path


# RAG Configuration Class
class RAGConfig:
    """Centralized RAG system configuration."""

    def __init__(self) -> None:
        """Initialize RAG configuration from environment variables."""
        # LLM Models
        self.llm_model = os.getenv("RAG_LLM_MODEL", "gpt-4o-mini")

        # Embedding Configuration
        self.embedding_model = os.getenv("RAG_EMBEDDING_MODEL", "text-embedding-3-small")
        self.embedding_dim = int(os.getenv("RAG_EMBEDDING_OUTPUT_DIM", "1536"))
        self.embed_instruction = os.getenv("RAG_EMBED_INSTRUCTION", "Represent the query for semantic retrieval:")

        # Chunking Configuration
        self.chunk_size = int(os.getenv("RAG_CHUNK_SIZE", "1000"))
        self.chunk_overlap = int(os.getenv("RAG_CHUNK_OVERLAP", "100"))

        # Search Configuration
        self.top_k = int(os.getenv("RAG_TOP_K", "50"))
        self.rerank_k = int(os.getenv("RAG_RERANK_K", "5"))

        # Reranker Configuration
        self.rerank_model = os.getenv("RAG_RERANK_MODEL", "Qwen3-Reranker-0.6B")
        self.rerank_enabled = os.getenv("RAG_RERANK_ENABLED", "false").lower() == "true"

        # Storage Configuration
        self.keep_original_files = os.getenv("RAG_KEEP_ORIGINAL_FILES", "true").lower() == "true"
        self.cold_storage_days = int(os.getenv("RAG_COLD_STORAGE_DAYS", "90"))

        # File Storage Paths
        self.upload_dir = Path("uploads/roadmap_docs")
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    @property
    def words_per_chunk(self) -> int:
        """Estimate words per chunk (1 token ≈ 0.75 words)."""
        return int(self.chunk_size * 0.75)

    @property
    def words_overlap(self) -> int:
        """Estimate overlap in words."""
        return int(self.chunk_overlap * 0.75)

    def validate_config(self) -> None:
        """Validate RAG configuration on startup.
        
        Raises
        ------
            ValueError: If configuration is invalid
        """
        # Validate model format
        if not self.llm_model:
            raise ValueError("RAG_LLM_MODEL environment variable is required")

        if not self.embedding_model:
            raise ValueError("RAG_EMBEDDING_MODEL environment variable is required")

        # Check if models follow provider/model format
        if "/" in self.llm_model:
            provider, model = self.llm_model.split("/", 1)
            if not provider or not model:
                raise ValueError(f"Invalid LLM model format: {self.llm_model}. Expected format: provider/model-name")

        if "/" in self.embedding_model:
            provider, model = self.embedding_model.split("/", 1)
            if not provider or not model:
                raise ValueError(f"Invalid embedding model format: {self.embedding_model}. Expected format: provider/model-name")

        # Validate embedding dimensions
        if self.embedding_dim <= 0:
            raise ValueError(f"Invalid embedding dimensions: {self.embedding_dim}. Must be positive.")

        # Validate chunk settings
        if self.chunk_size <= 0:
            raise ValueError(f"Invalid chunk size: {self.chunk_size}. Must be positive.")

        if self.chunk_overlap < 0:
            raise ValueError(f"Invalid chunk overlap: {self.chunk_overlap}. Must be non-negative.")

        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(f"Chunk overlap ({self.chunk_overlap}) must be less than chunk size ({self.chunk_size}).")

        # Validate search settings
        if self.top_k <= 0:
            raise ValueError(f"Invalid top_k: {self.top_k}. Must be positive.")

        if self.rerank_k <= 0:
            raise ValueError(f"Invalid rerank_k: {self.rerank_k}. Must be positive.")

        if self.rerank_k > self.top_k:
            raise ValueError(f"rerank_k ({self.rerank_k}) cannot be greater than top_k ({self.top_k}).")


# Global RAG configuration instance
rag_config = RAGConfig()

# Tag categories for classification
TAG_CATEGORIES = {
    "language": ["python", "javascript", "java", "cpp", "go", "rust", "ruby", "php", "swift", "kotlin", "r", "matlab"],
    "framework": [
        "react",
        "angular",
        "vue",
        "django",
        "flask",
        "spring",
        "express",
        "rails",
        "laravel",
        "tensorflow",
        "pytorch",
    ],
    "domain": [
        "web-development",
        "machine-learning",
        "data-science",
        "mobile-development",
        "devops",
        "cloud-computing",
        "cybersecurity",
        "blockchain",
    ],
    "database": ["sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "cassandra"],
    "tool": ["git", "docker", "kubernetes", "jenkins", "aws", "azure", "gcp", "linux", "bash"],
    "concept": [
        "algorithms",
        "data-structures",
        "testing",
        "deployment",
        "api-design",
        "microservices",
        "design-patterns",
    ],
}

# Default colors for tag categories (hex format)
TAG_CATEGORY_COLORS = {
    "language": "#3B82F6",  # Blue
    "framework": "#10B981",  # Green
    "domain": "#8B5CF6",  # Purple
    "database": "#F59E0B",  # Amber
    "tool": "#EF4444",  # Red
    "concept": "#6B7280",  # Gray
    "default": "#6366F1",  # Indigo
}
