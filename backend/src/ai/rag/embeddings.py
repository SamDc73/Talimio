"""Vector-based RAG implementation using LiteLLM embeddings and pgvector."""

import asyncio
import json
import logging
import math
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import batched
from typing import cast

import litellm
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.litellm_config import configure_litellm
from src.ai.rag.config import get_rag_config
from src.ai.rag.exceptions import RagUnavailableError, RagValidationError
from src.ai.rag.schemas import SearchResult


logger = logging.getLogger(__name__)
configure_litellm()

_LITELLM_PROVIDER_ERROR_TYPES = (
    litellm.APIError,
    litellm.APIConnectionError,
    litellm.AuthenticationError,
    litellm.BadGatewayError,
    litellm.BadRequestError,
    litellm.BudgetExceededError,
    litellm.ContentPolicyViolationError,
    litellm.ContextWindowExceededError,
    litellm.InternalServerError,
    litellm.InvalidRequestError,
    litellm.NotFoundError,
    litellm.RouterRateLimitError,
    litellm.ServiceUnavailableError,
    litellm.UnprocessableEntityError,
    litellm.UnsupportedParamsError,
)

_EMBEDDING_RUNTIME_ERROR_TYPES = (
    TimeoutError,
    asyncio.TimeoutError,
    ConnectionError,
    OSError,
    litellm.Timeout,
    *_LITELLM_PROVIDER_ERROR_TYPES,
)

_VECTOR_SEARCH_FALLBACK_ERROR_TYPES = (
    SQLAlchemyError,
    *_EMBEDDING_RUNTIME_ERROR_TYPES,
)
_NEIGHBOR_CONTEXT_WINDOW = 1
_NEIGHBOR_CONTEXT_MAX_CHARS = 5_500
_HYBRID_CANDIDATE_MULTIPLIER = 4
_RRF_K = 60


@dataclass
class _FusedSearchItem:
    doc_id: str
    doc_type: str
    chunk_index: int
    content: str
    metadata: dict[str, object]
    fused_score: float = 0.0
    dense_score: float | None = None
    lexical_score: float | None = None
    dense_rank: int | None = None
    lexical_rank: int | None = None

    def score_metadata(self) -> dict[str, object]:
        metadata: dict[str, object] = {"fused_score": self.fused_score}
        if self.dense_score is not None:
            metadata["dense_score"] = self.dense_score
        if self.lexical_score is not None:
            metadata["lexical_score"] = self.lexical_score
        if self.dense_rank is not None:
            metadata["dense_rank"] = self.dense_rank
        if self.lexical_rank is not None:
            metadata["lexical_rank"] = self.lexical_rank
        return metadata


def _is_json_value(value: object) -> bool:
    if isinstance(value, float) and not math.isfinite(value):
        return False
    if value is None or isinstance(value, str | int | float | bool):
        return True
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return all(_is_json_value(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _is_json_value(item) for key, item in value.items())
    return False


class VectorRAG:
    """Vector-based RAG using LiteLLM embeddings and pgvector."""

    def __init__(self) -> None:
        """Initialize LiteLLM configuration and caching helpers."""
        config = get_rag_config()
        self.embedding_model = config.embedding_model
        if not self.embedding_model:
            message = "RAG embedding model not configured (set RAG_EMBEDDING_MODEL)"
            raise RagUnavailableError(message)

        self.configured_embedding_dim = config.embedding_output_dim
        self.embedding_context_size = config.embedding_context_size
        self.manual_retry_attempts = config.embedding_manual_retries
        self.retry_backoff_seconds = config.embedding_retry_delay_seconds
        self.batch_size = config.embedding_batch_size

        self._db_embedding_dim: int | None = None
        self._effective_embedding_dim: int | None = self.configured_embedding_dim
        self._dimensions_validated = False

        logger.debug(
            "rag.vector.initialized",
            extra={
                "model": self.embedding_model,
                "configured_dim": self.configured_embedding_dim,
                "batch_size": self.batch_size,
                "context_size": self.embedding_context_size,
            },
        )

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for a single text input."""
        embeddings = await self._embed_texts([text])
        return embeddings[0]

    async def generate_embeddings(self, texts: Sequence[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        return await self._embed_texts(texts)

    async def store_document_chunks_with_embeddings(
        self,
        session: AsyncSession,
        *,
        doc_type: str,
        doc_id: uuid.UUID,
        title: str,
        chunks: Sequence[str],
        course_id: uuid.UUID | None = None,
        extra_metadata: dict[str, object] | None = None,
        per_chunk_metadata: Sequence[dict[str, object]] | None = None,
    ) -> None:
        """Store document chunks with their embeddings in pgvector."""
        try:
            await self._ensure_dimensions(session)

            chunk_payloads: list[tuple[int, str, dict[str, JsonValue]]] = []
            total_chunks = len(chunks)
            for index, raw_chunk in enumerate(chunks):
                chunk_text = raw_chunk.strip()
                if not chunk_text:
                    continue

                metadata: dict[str, object] = {
                    "title": title,
                    "chunk_index": index,
                    "total_chunks": total_chunks,
                }
                if course_id:
                    metadata["course_id"] = str(course_id)
                if extra_metadata:
                    metadata.update(extra_metadata)
                if per_chunk_metadata and index < len(per_chunk_metadata):
                    metadata.update(per_chunk_metadata[index])

                normalized_metadata = self._normalize_metadata(metadata)
                chunk_payloads.append((index, chunk_text, normalized_metadata))

            if not chunk_payloads:
                logger.warning("No valid chunks to store for doc_id=%s doc_type=%s", doc_id, doc_type)
                message = "No valid chunks to store"
                raise RagValidationError(message)

            logger.info(
                "Storing %s chunks for doc_id=%s doc_type=%s (batch_size=%s)",
                len(chunk_payloads),
                doc_id,
                doc_type,
                self.batch_size,
            )

            for batch in batched(chunk_payloads, self.batch_size, strict=False):
                texts = [payload[1] for payload in batch]
                embeddings = await self._embed_texts(texts)

                for (chunk_index, chunk_text, chunk_metadata), embedding in zip(batch, embeddings, strict=True):
                    embedding_str = self._format_vector(embedding)
                    await session.execute(
                        text(
                            """
                            INSERT INTO rag_document_chunks
                            (doc_id, doc_type, chunk_index, content, metadata, embedding, created_at)
                            VALUES (:doc_id, :doc_type, :chunk_index, :content, CAST(:metadata AS jsonb),
                                    CAST(:embedding AS vector), NOW())
                            ON CONFLICT (doc_id, chunk_index)
                            DO UPDATE SET
                                content = EXCLUDED.content,
                                metadata = EXCLUDED.metadata,
                                embedding = EXCLUDED.embedding
                            """
                        ),
                        {
                            "doc_id": str(doc_id),
                            "doc_type": doc_type,
                            "chunk_index": chunk_index,
                            "content": chunk_text,
                            "metadata": json.dumps(chunk_metadata),
                            "embedding": embedding_str,
                        },
                    )

            await session.flush()
            logger.info(
                "Persisted %s chunks for doc_id=%s doc_type=%s",
                len(chunk_payloads),
                doc_id,
                doc_type,
            )

        except (SQLAlchemyError, RagUnavailableError, RagValidationError, *_EMBEDDING_RUNTIME_ERROR_TYPES):
            logger.exception("Failed to store chunks with embeddings for doc_id=%s", doc_id)
            raise

    async def search(
        self,
        session: AsyncSession,
        *,
        doc_type: str,
        query: str,
        limit: int = 5,
        doc_id: uuid.UUID | None = None,
        course_id: uuid.UUID | None = None,
    ) -> list[SearchResult]:
        """Perform hybrid dense and lexical search scoped to optional identifiers."""
        try:
            await self._ensure_dimensions(session)
            query_embedding = await self.generate_embedding(query)
            embedding_str = self._format_vector(query_embedding)
            candidate_limit = limit * _HYBRID_CANDIDATE_MULTIPLIER

            where_sql, scope_params = self._build_search_scope(doc_type=doc_type, doc_id=doc_id, course_id=course_id)

            params: dict[str, object] = {
                **scope_params,
                "query": query,
                "query_embedding": embedding_str,
                "candidate_limit": candidate_limit,
            }

            # Ensure HNSW search quality is configurable per-query
            # Requires a transaction; SQLAlchemy manages one per session usage
            # Note: PostgreSQL does not allow bind parameters in SET statements.
            # Use a validated literal integer to avoid syntax errors like
            # "syntax error at or near $1" from psycopg.
            ef_val = get_rag_config().hnsw_ef_search
            await session.execute(text(f"SET LOCAL hnsw.ef_search = {ef_val}"))

            dense_result = await session.execute(text(self._build_dense_search_sql(where_sql)), params)
            lexical_result = await session.execute(text(self._build_lexical_search_sql(where_sql)), params)
            rows = self._fuse_search_rows(dense_result.mappings().all(), lexical_result.mappings().all(), limit)

            search_results: list[SearchResult] = []
            for row in rows:
                metadata = self._normalize_metadata({**row.metadata, **row.score_metadata()})
                content = await self._expand_search_result_content(
                    session=session,
                    doc_type=doc_type,
                    doc_id=row.doc_id,
                    chunk_index=row.chunk_index,
                    content=row.content,
                    metadata=metadata,
                )
                search_results.append(
                    SearchResult(
                        chunk_id=f"{row.doc_id}_{row.chunk_index}",
                        content=content,
                        similarity_score=row.fused_score,
                        metadata=metadata,
                    )
                )

            logger.debug(
                "Vector search retrieved %s results for doc_type=%s doc_id=%s course_id=%s",
                len(search_results),
                doc_type,
                doc_id,
                course_id,
            )
            return search_results

        except _VECTOR_SEARCH_FALLBACK_ERROR_TYPES as error:
            logger.exception("Vector search failed for doc_type=%s doc_id=%s", doc_type, doc_id)
            message = "RAG vector search is unavailable"
            raise RagUnavailableError(message) from error

    @staticmethod
    def _build_search_scope(
        *, doc_type: str, doc_id: uuid.UUID | None, course_id: uuid.UUID | None
    ) -> tuple[str, dict[str, object]]:
        predicates = ["doc_type = :doc_type"]
        params: dict[str, object] = {"doc_type": doc_type}

        if doc_id:
            predicates.append("doc_id = :doc_id")
            params["doc_id"] = str(doc_id)
        if course_id:
            predicates.append("metadata->>'course_id' = :course_id")
            params["course_id"] = str(course_id)

        return " AND ".join(predicates), params

    @staticmethod
    def _build_dense_search_sql(where_sql: str) -> str:
        return """
            SELECT
                doc_id,
                doc_type,
                chunk_index,
                content,
                metadata,
                1 - (embedding <=> CAST(:query_embedding AS vector)) AS dense_score
            FROM rag_document_chunks
            WHERE __SEARCH_SCOPE__
              AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:query_embedding AS vector)
            LIMIT :candidate_limit
        """.replace("__SEARCH_SCOPE__", where_sql)

    @staticmethod
    def _build_lexical_search_sql(where_sql: str) -> str:
        return """
            WITH lexical_query AS (
                SELECT websearch_to_tsquery('english', :query) AS query
            )
            SELECT
                doc_id,
                doc_type,
                chunk_index,
                content,
                metadata,
                ts_rank_cd(to_tsvector('english', content), lexical_query.query) AS lexical_score
            FROM rag_document_chunks, lexical_query
            WHERE __SEARCH_SCOPE__
              AND to_tsvector('english', content) @@ lexical_query.query
            ORDER BY lexical_score DESC, chunk_index
            LIMIT :candidate_limit
        """.replace("__SEARCH_SCOPE__", where_sql)

    def _fuse_search_rows(
        self, dense_rows: Sequence[RowMapping], lexical_rows: Sequence[RowMapping], limit: int
    ) -> list[_FusedSearchItem]:
        fused: dict[tuple[str, int], _FusedSearchItem] = {}

        for rank, row in enumerate(dense_rows, start=1):
            item = self._get_fused_item(fused, row)
            item.dense_rank = rank
            item.dense_score = float(row["dense_score"])
            item.fused_score += self._rrf_score(rank)

        for rank, row in enumerate(lexical_rows, start=1):
            item = self._get_fused_item(fused, row)
            item.lexical_rank = rank
            item.lexical_score = float(row["lexical_score"])
            item.fused_score += self._rrf_score(rank)

        ranked_rows = sorted(
            fused.values(),
            key=lambda item: (item.fused_score, item.lexical_score or 0.0),
            reverse=True,
        )
        return ranked_rows[:limit]

    @staticmethod
    def _get_fused_item(fused: dict[tuple[str, int], _FusedSearchItem], row: RowMapping) -> _FusedSearchItem:
        key = (str(row["doc_id"]), int(row["chunk_index"]))
        if key not in fused:
            metadata = dict(row["metadata"]) if isinstance(row["metadata"], dict) else {}
            fused[key] = _FusedSearchItem(
                doc_id=key[0],
                doc_type=str(row["doc_type"]),
                chunk_index=key[1],
                content=str(row["content"]),
                metadata=metadata,
            )
        return fused[key]

    @staticmethod
    def _rrf_score(rank: int) -> float:
        return 1.0 / (_RRF_K + rank)

    async def _expand_search_result_content(
        self,
        *,
        session: AsyncSession,
        doc_type: str,
        doc_id: str,
        chunk_index: int,
        content: str,
        metadata: dict[str, JsonValue],
    ) -> str:
        """Add adjacent same-section chunks for structured document retrieval."""
        if metadata.get("contextualized") is not True:
            return content

        result = await session.execute(
            text(
                """
                SELECT chunk_index, content, metadata
                FROM rag_document_chunks
                WHERE doc_type = :doc_type
                  AND doc_id = :doc_id
                  AND chunk_index BETWEEN :start_index AND :end_index
                ORDER BY chunk_index
                """
            ),
            {
                "doc_type": doc_type,
                "doc_id": doc_id,
                "start_index": chunk_index - _NEIGHBOR_CONTEXT_WINDOW,
                "end_index": chunk_index + _NEIGHBOR_CONTEXT_WINDOW,
            },
        )

        section_path = metadata.get("section_path")
        parts: list[str] = []
        for row in result.fetchall():
            row_metadata = dict(row.metadata) if isinstance(row.metadata, dict) else {}
            row_section_path = row_metadata.get("section_path")
            if row.chunk_index != chunk_index and section_path and row_section_path != section_path:
                continue
            parts.append(str(row.content).strip())

        expanded_content = "\n\n".join(part for part in parts if part)
        if not expanded_content or len(expanded_content) > _NEIGHBOR_CONTEXT_MAX_CHARS:
            return content
        return expanded_content

    async def _ensure_dimensions(self, session: AsyncSession) -> None:
        """Validate embedding dimensions against database schema."""
        if self._dimensions_validated:
            return

        db_dim = await self._fetch_db_embedding_dimension(session)

        if db_dim is not None and self.configured_embedding_dim is not None and db_dim != self.configured_embedding_dim:
            message = (
                f"Embedding dimension mismatch detected: model={self.configured_embedding_dim} database={db_dim}. "
                "Run scripts/verify_rag_schema.py or align RAG_EMBEDDING_OUTPUT_DIM."
            )
            logger.error(
                "rag.embeddings.dimension_mismatch",
                extra={"configured_dimension": self.configured_embedding_dim, "database_dimension": db_dim},
            )
            raise RagUnavailableError(message)

        if db_dim is not None:
            self._db_embedding_dim = db_dim

        self._dimensions_validated = True
        logger.info(
            "Embedding dimensions validated (model=%s database=%s)",
            self._effective_embedding_dim,
            self._db_embedding_dim,
        )

    async def _fetch_db_embedding_dimension(self, session: AsyncSession) -> int | None:
        """Read the embedding column dimension from pgvector metadata."""
        result = await session.execute(
            text(
                """
                SELECT atttypmod AS dimension
                FROM pg_attribute
                WHERE attrelid = 'rag_document_chunks'::regclass
                  AND attname = 'embedding'
                """
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            logger.warning("Could not determine rag_document_chunks.embedding dimension from database")
            return None

        if row <= 0:
            logger.warning("Database embedding dimension appears invalid: %s", row)
            return None

        logger.debug("Database embedding dimension detected: %s", row)
        return int(row)

    async def _embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed a batch of texts with manual retries."""
        if not texts:
            return []

        embed_kwargs = self._build_embedding_kwargs(texts)
        attempts = self.manual_retry_attempts + 1

        for attempt in range(1, attempts + 1):
            try:
                response = await self._invoke_embedding(embed_kwargs)
                embeddings = self._normalize_embedding_response(response)
                if len(embeddings) != len(texts):
                    message = "Embedding provider returned an unexpected number of embeddings"
                    raise RagUnavailableError(message)
                logger.debug("Generated %s embeddings (attempt %s)", len(embeddings), attempt)
                return embeddings
            except _EMBEDDING_RUNTIME_ERROR_TYPES as exc:
                last_attempt = attempt == attempts
                if last_attempt:
                    logger.exception("Failed to generate embeddings after %s attempts", attempts)
                    raise

                delay_seconds = self.retry_backoff_seconds * math.pow(2, attempt - 1)
                logger.warning(
                    "Embedding call failed on attempt %s/%s (%s). Retrying in %.2fs",
                    attempt,
                    attempts,
                    exc,
                    delay_seconds,
                )
                await asyncio.sleep(delay_seconds)

        message = "Exhausted embedding retries unexpectedly"
        raise RagUnavailableError(message)

    def _build_embedding_kwargs(self, texts: Sequence[str]) -> dict[str, object]:
        """Construct kwargs for LiteLLM embedding call."""
        embed_kwargs: dict[str, object] = {
            "model": self.embedding_model,
            "input": list(texts),
            "timeout": 30,
            "max_retries": 0,
        }

        if self.configured_embedding_dim:
            embed_kwargs["dimensions"] = self.configured_embedding_dim

        if self.embedding_context_size and self.embedding_model.startswith("ollama/"):
            embed_kwargs["num_ctx"] = self.embedding_context_size

        return embed_kwargs

    async def _invoke_embedding(self, embed_kwargs: dict[str, object]) -> litellm.EmbeddingResponse:
        """Call LiteLLM embedding endpoint."""
        return await litellm.aembedding(**embed_kwargs)

    @staticmethod
    def _normalize_embedding_response(response: litellm.EmbeddingResponse) -> list[list[float]]:
        """Normalize LiteLLM embedding response to list of float vectors."""
        try:
            normalized_embeddings: list[list[float]] = []
            for item in response.data:
                embedding = item.embedding
                if isinstance(embedding, (str, bytes)):
                    message = "Embedding provider returned a malformed response"
                    raise RagUnavailableError(message)
                normalized_embedding = [float(value) for value in embedding]
                if not normalized_embedding or any(not math.isfinite(value) for value in normalized_embedding):
                    message = "Embedding provider returned a malformed response"
                    raise RagUnavailableError(message)
                normalized_embeddings.append(normalized_embedding)
            return normalized_embeddings
        except (AttributeError, TypeError, ValueError) as error:
            message = "Embedding provider returned a malformed response"
            raise RagUnavailableError(message) from error

    @staticmethod
    def _format_vector(values: Sequence[float]) -> str:
        """Format embedding sequence for pgvector insertion."""
        return "[" + ",".join(str(value) for value in values) + "]"

    @staticmethod
    def _normalize_metadata(metadata: dict[str, object]) -> dict[str, JsonValue]:
        """Ensure metadata values are JSON-serializable."""
        normalized: dict[str, JsonValue] = {}
        for key, value in metadata.items():
            if isinstance(value, uuid.UUID):
                normalized[key] = str(value)
            elif isinstance(value, float) and not math.isfinite(value):
                message = f"Metadata field '{key}' must be a finite number"
                raise RagValidationError(message)
            elif _is_json_value(value):
                normalized[key] = cast("JsonValue", value)
            else:
                message = f"Metadata field '{key}' contains an unsupported value"
                raise RagValidationError(message)
        return normalized
