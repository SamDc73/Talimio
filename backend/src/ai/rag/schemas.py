"""RAG system Pydantic schemas."""

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from src.config.schema_casing import build_camel_config


class SearchRequest(BaseModel):
    """Schema for RAG search request."""

    query: str = Field(min_length=1, description="Search query")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results to return")

    model_config = build_camel_config()

    @field_validator("query")
    @classmethod
    def _query_must_contain_text(cls, value: str) -> str:
        if value.strip():
            return value
        message = "Search query must not be empty"
        raise ValueError(message)


class SearchResult(BaseModel):
    """Schema for RAG search result."""

    chunk_id: str = Field(description="Unique chunk identifier")
    content: str = Field(description="Chunk text content")
    similarity_score: float = Field(description="Retrieval or rerank score used for result ordering")
    metadata: dict[str, JsonValue] = Field(default_factory=dict, description="Chunk metadata")

    model_config = build_camel_config()


class MultiViewQueryExpansion(BaseModel):
    """Structured retrieval query perspectives for lesson RAG."""

    conceptual: str = Field(min_length=1)
    practical: str = Field(min_length=1)
    technical: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class UtilityBatchFilterResponse(BaseModel):
    """Structured utility filter result for retrieved chunks."""

    useful_indices: list[int] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class SearchResponse(BaseModel):
    """Schema for RAG search response."""

    results: list[SearchResult]
    total: int

    model_config = build_camel_config()


class DefaultResponse(BaseModel):
    """Standard response following best practices."""

    status: bool
    message: str
    details: dict[str, JsonValue] = Field(default_factory=dict)

    model_config = build_camel_config()
