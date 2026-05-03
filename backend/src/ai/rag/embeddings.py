"""Vector-based RAG implementation using LiteLLM embeddings and pgvector."""

import asyncio
import json
import logging
import math
import uuid
from collections.abc import Iterator, Sequence
from typing import cast

import litellm
from pydantic import JsonValue
from sqlalchemy import text
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

            for batch in self._batched(chunk_payloads, self.batch_size):
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
        """Perform a similarity search scoped to optional identifiers."""
        try:
            await self._ensure_dimensions(session)
            query_embedding = await self.generate_embedding(query)
            embedding_str = self._format_vector(query_embedding)

            params: dict[str, object] = {
                "doc_type": doc_type,
                "query_embedding": embedding_str,
                "limit": limit,
            }

            if doc_id:
                params["doc_id"] = str(doc_id)
            if course_id:
                params["course_id"] = str(course_id)

            # Ensure HNSW search quality is configurable per-query
            # Requires a transaction; SQLAlchemy manages one per session usage
            # Note: PostgreSQL does not allow bind parameters in SET statements.
            # Use a validated literal integer to avoid syntax errors like
            # "syntax error at or near $1" from psycopg.
            ef_val = get_rag_config().hnsw_ef_search
            await session.execute(text(f"SET LOCAL hnsw.ef_search = {ef_val}"))

            if doc_id and course_id:
                query_sql = """
                    SELECT
                        doc_id,
                        doc_type,
                        chunk_index,
                        content,
                        metadata,
                        1 - (embedding <=> CAST(:query_embedding AS vector)) AS similarity
                    FROM rag_document_chunks
                    WHERE doc_type = :doc_type
                      AND embedding IS NOT NULL
                      AND doc_id = :doc_id
                      AND metadata->>'course_id' = :course_id
                    ORDER BY embedding <=> CAST(:query_embedding AS vector)
                    LIMIT :limit
                """
            elif doc_id:
                query_sql = """
                    SELECT
                        doc_id,
                        doc_type,
                        chunk_index,
                        content,
                        metadata,
                        1 - (embedding <=> CAST(:query_embedding AS vector)) AS similarity
                    FROM rag_document_chunks
                    WHERE doc_type = :doc_type
                      AND embedding IS NOT NULL
                      AND doc_id = :doc_id
                    ORDER BY embedding <=> CAST(:query_embedding AS vector)
                    LIMIT :limit
                """
            elif course_id:
                query_sql = """
                    SELECT
                        doc_id,
                        doc_type,
                        chunk_index,
                        content,
                        metadata,
                        1 - (embedding <=> CAST(:query_embedding AS vector)) AS similarity
                    FROM rag_document_chunks
                    WHERE doc_type = :doc_type
                      AND embedding IS NOT NULL
                      AND metadata->>'course_id' = :course_id
                    ORDER BY embedding <=> CAST(:query_embedding AS vector)
                    LIMIT :limit
                """
            else:
                query_sql = """
                    SELECT
                        doc_id,
                        doc_type,
                        chunk_index,
                        content,
                        metadata,
                        1 - (embedding <=> CAST(:query_embedding AS vector)) AS similarity
                    FROM rag_document_chunks
                    WHERE doc_type = :doc_type
                      AND embedding IS NOT NULL
                    ORDER BY embedding <=> CAST(:query_embedding AS vector)
                    LIMIT :limit
                """
            result = await session.execute(
                text(query_sql),
                params,
            )

            rows = result.fetchall()
            search_results: list[SearchResult] = []
            for row in rows:
                row_metadata = dict(row.metadata) if isinstance(row.metadata, dict) else {}
                metadata = self._normalize_metadata(row_metadata)
                similarity = float(row.similarity)
                content = await self._expand_search_result_content(
                    session=session,
                    doc_type=doc_type,
                    doc_id=str(row.doc_id),
                    chunk_index=int(row.chunk_index),
                    content=str(row.content),
                    metadata=metadata,
                )
                search_results.append(
                    SearchResult(
                        chunk_id=f"{row.doc_id}_{row.chunk_index}",
                        content=content,
                        similarity_score=similarity,
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

    # Removed legacy helpers that are now handled by RAG service + chonkie

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
        if not hasattr(self, "_dimensions_validated"):
            self._dimensions_validated = False
        if not hasattr(self, "_effective_embedding_dim"):
            self._effective_embedding_dim = getattr(self, "configured_embedding_dim", None)
        if not hasattr(self, "_db_embedding_dim"):
            self._db_embedding_dim = None
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

    async def _invoke_embedding(self, embed_kwargs: dict[str, object]) -> object:
        """Call LiteLLM embedding endpoint."""
        return await litellm.aembedding(**embed_kwargs)

    @staticmethod
    def _normalize_embedding_response(response: object) -> list[list[float]]:
        """Normalize LiteLLM embedding response to list of float vectors."""
        data = getattr(response, "data", None)
        embeddings = [item.get("embedding", item) for item in data] if data else response

        if not isinstance(embeddings, Sequence):
            message = f"Unexpected embedding response type: {type(embeddings)}"
            raise RagUnavailableError(message)

        normalized_embeddings: list[list[float]] = []
        for embedding in embeddings:
            if not embedding or not isinstance(embedding, Sequence):
                message = f"Invalid embedding payload of type {type(embedding)}"
                raise RagUnavailableError(message)
            normalized_embedding: list[float] = []
            for value in embedding:
                if not isinstance(value, (str, int, float)):
                    message = f"Invalid embedding value of type {type(value)}"
                    raise RagUnavailableError(message)
                normalized_embedding.append(float(value))
            normalized_embeddings.append(normalized_embedding)

        return normalized_embeddings

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

    @staticmethod
    def _batched(
        sequence: Sequence[tuple[int, str, dict[str, JsonValue]]], batch_size: int
    ) -> Iterator[list[tuple[int, str, dict[str, JsonValue]]]]:
        """Yield fixed-size batches from sequence."""
        if batch_size <= 1:
            for item in sequence:
                yield [item]
            return

        for start in range(0, len(sequence), batch_size):
            yield list(sequence[start : start + batch_size])
