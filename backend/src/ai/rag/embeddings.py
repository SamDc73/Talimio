"""Vector-based RAG implementation using LiteLLM embeddings and pgvector."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import uuid
from collections.abc import Iterator, Sequence
from typing import TYPE_CHECKING, Any

import litellm
from sqlalchemy import text

from src.ai.rag.config import rag_config


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.rag.schemas import SearchResult


logger = logging.getLogger(__name__)


class VectorRAG:
    """Vector-based RAG using LiteLLM embeddings and pgvector."""

    def __init__(self) -> None:
        """Initialize LiteLLM configuration and caching helpers."""
        # Prefer centralized config (env prefix RAG_ already supported by pydantic BaseSettings)
        self.embedding_model = rag_config.embedding_model
        if not self.embedding_model:
            error_msg = "RAG embedding model not configured (set RAG_EMBEDDING_MODEL)"
            raise ValueError(error_msg)

        self.configured_embedding_dim = rag_config.embedding_output_dim
        self.embedding_context_size = rag_config.embedding_context_size
        self.manual_retry_attempts = max(rag_config.embedding_manual_retries, 0)
        self.retry_backoff_seconds = max(rag_config.embedding_retry_delay_seconds, 0.0)
        self.batch_size = max(rag_config.embedding_batch_size, 1)

        self._db_embedding_dim: int | None = None
        self._effective_embedding_dim: int | None = self.configured_embedding_dim
        self._dimensions_validated = False

        logger.info(
            "VectorRAG initialized with model=%s configured_dim=%s batch_size=%s context_size=%s",
            self.embedding_model,
            self.configured_embedding_dim,
            self.batch_size,
            self.embedding_context_size,
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
        extra_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store document chunks with their embeddings in pgvector."""
        try:
            await self._ensure_dimensions(session)

            chunk_payloads: list[tuple[int, str, dict[str, Any]]] = []
            total_chunks = len(chunks)
            for index, raw_chunk in enumerate(chunks):
                chunk_text = raw_chunk.strip()
                if not chunk_text:
                    continue

                metadata: dict[str, Any] = {
                    "title": title,
                    "chunk_index": index,
                    "total_chunks": total_chunks,
                }
                if course_id:
                    metadata["course_id"] = str(course_id)
                if extra_metadata:
                    metadata.update(extra_metadata)

                metadata = self._normalize_metadata(metadata)
                chunk_payloads.append((index, chunk_text, metadata))

            if not chunk_payloads:
                logger.warning("No valid chunks to store for doc_id=%s doc_type=%s", doc_id, doc_type)
                return

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

                for (chunk_index, chunk_text, metadata), embedding in zip(batch, embeddings, strict=True):
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
                            "metadata": json.dumps(metadata),
                            "embedding": embedding_str,
                        },
                    )

            await session.commit()
            logger.info(
                "Persisted %s chunks for doc_id=%s doc_type=%s",
                len(chunk_payloads),
                doc_id,
                doc_type,
            )

        except Exception:
            logger.exception("Failed to store chunks with embeddings for doc_id=%s", doc_id)
            await session.rollback()
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

            filters: list[str] = ["doc_type = :doc_type", "embedding IS NOT NULL"]
            params: dict[str, Any] = {
                "doc_type": doc_type,
                "query_embedding": embedding_str,
                "limit": limit,
            }

            if doc_id:
                filters.append("doc_id = :doc_id")
                params["doc_id"] = str(doc_id)
            if course_id:
                filters.append("metadata->>'course_id' = :course_id")
                params["course_id"] = str(course_id)

            # Ensure HNSW search quality is configurable per-query
            # Requires a transaction; SQLAlchemy manages one per session usage
            # Note: PostgreSQL does not allow bind parameters in SET statements.
            # Use a validated literal integer to avoid syntax errors like
            # "syntax error at or near $1" from psycopg.
            ef_val = int(rag_config.hnsw_ef_search)
            await session.execute(text(f"SET LOCAL hnsw.ef_search = {ef_val}"))

            filter_clause = " AND ".join(filters)
            result = await session.execute(
                text(
                    f"""
                    SELECT
                        doc_id,
                        doc_type,
                        chunk_index,
                        content,
                        metadata,
                        1 - (embedding <=> CAST(:query_embedding AS vector)) AS similarity
                    FROM rag_document_chunks
                    WHERE {filter_clause}
                    ORDER BY embedding <=> CAST(:query_embedding AS vector)
                    LIMIT :limit
                    """
                ),
                params,
            )

            rows = result.fetchall()
            search_results: list[SearchResult] = []
            for row in rows:
                row_metadata = dict(row.metadata) if isinstance(row.metadata, dict) else {}
                metadata = self._normalize_metadata(row_metadata)
                similarity = row.similarity if row.similarity and row.similarity > 0 else 0.1
                search_results.append(
                    SearchResult(
                        chunk_id=f"{row.doc_id}_{row.chunk_index}",
                        content=row.content,
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

        except Exception:
            logger.exception("Vector search failed for doc_type=%s doc_id=%s", doc_type, doc_id)
            return []

    # Removed legacy helpers that are now handled by RAG service + chonkie

    async def _ensure_dimensions(self, session: AsyncSession) -> None:
        """Validate embedding dimensions against database schema."""
        if self._dimensions_validated:
            return

        db_dim = await self._fetch_db_embedding_dimension(session)

        if db_dim is not None and self.configured_embedding_dim is not None and db_dim != self.configured_embedding_dim:
            error_msg = (
                f"Embedding dimension mismatch detected: model={self.configured_embedding_dim} database={db_dim}. "
                "Run scripts/verify_rag_schema.py or align RAG_EMBEDDING_OUTPUT_DIM."
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

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
                logger.debug("Generated %s embeddings (attempt %s)", len(embeddings), attempt)
                return embeddings
            except Exception as exc:
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

        msg = "Exhausted embedding retries unexpectedly"
        raise RuntimeError(msg)

    def _build_embedding_kwargs(self, texts: Sequence[str]) -> dict[str, Any]:
        """Construct kwargs for LiteLLM embedding call."""
        embed_kwargs: dict[str, Any] = {
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

    async def _invoke_embedding(self, embed_kwargs: dict[str, Any]) -> Any:
        """Call LiteLLM embedding endpoint."""
        return await litellm.aembedding(**embed_kwargs)

    @staticmethod
    def _normalize_embedding_response(response: Any) -> list[list[float]]:
        """Normalize LiteLLM embedding response to list of float vectors."""
        data = getattr(response, "data", None)
        embeddings = [item.get("embedding", item) for item in data] if data else response

        if not isinstance(embeddings, Sequence):
            msg = f"Unexpected embedding response type: {type(embeddings)}"
            raise TypeError(msg)

        normalized_embeddings: list[list[float]] = []
        for embedding in embeddings:
            if not embedding or not isinstance(embedding, Sequence):
                msg = f"Invalid embedding payload of type {type(embedding)}"
                raise ValueError(msg)
            normalized_embeddings.append([float(value) for value in embedding])

        return normalized_embeddings

    @staticmethod
    def _format_vector(values: Sequence[float]) -> str:
        """Format embedding sequence for pgvector insertion."""
        return "[" + ",".join(str(value) for value in values) + "]"

    @staticmethod
    def _normalize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
        """Ensure metadata values are JSON-serializable."""
        normalized: dict[str, Any] = {}
        for key, value in metadata.items():
            if isinstance(value, uuid.UUID):
                normalized[key] = str(value)
            else:
                normalized[key] = value
        return normalized

    @staticmethod
    def _batched(
        sequence: Sequence[tuple[int, str, dict[str, Any]]], batch_size: int
    ) -> Iterator[list[tuple[int, str, dict[str, Any]]]]:
        """Yield fixed-size batches from sequence."""
        if batch_size <= 1:
            for item in sequence:
                yield [item]
            return

        for start in range(0, len(sequence), batch_size):
            yield list(sequence[start : start + batch_size])
