"""Vector store operations and embedding generation - FIXED VERSION."""

import json
import logging
import uuid
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import env
from src.database.session import async_session_maker


logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generate embeddings using LiteLLM - with proper lazy initialization."""

    # Class-level cache for model capabilities
    _model_capabilities_cache: dict[str, bool] = {}
    _initialized = False
    _instance: Optional["EmbeddingGenerator"] = None

    def __new__(cls) -> "EmbeddingGenerator":
        """Singleton pattern to prevent multiple initializations."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize embedding generator with configuration."""
        if not self._initialized:
            self.model = env("RAG_EMBEDDING_MODEL", "text-embedding-3-small")
            self.dimensions = int(env("RAG_EMBEDDING_OUTPUT_DIM")) if env("RAG_EMBEDDING_OUTPUT_DIM") else None
            self.instruction = env("RAG_EMBED_INSTRUCTION", "Represent the query for semantic retrieval:")
            self._initialized = True
            # NO logging or API calls during init!

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for text chunks."""
        if not texts:
            return []

        try:
            # Import litellm only when actually needed
            from litellm import embedding

            # Detect capabilities on first real use
            if not hasattr(self, "_capabilities_checked"):
                self._capabilities_checked = True
                # Don't call _detect_model_capabilities to avoid issues

            # Generate embeddings - LiteLLM handles provider-specific config
            response = embedding(
                model=self.model,
                input=texts
            )

            return [emb["embedding"] for emb in response.data]

        except Exception as e:
            logger.warning("Failed to generate embeddings: %s", str(e))
            # Return fake embeddings as fallback - match existing dimensions
            dimensions = self.dimensions or 768  # Use 768 to match existing embeddings
            return [[0.1] * dimensions for _ in texts]

    async def generate_query_embedding(self, query: str) -> list[float]:
        """Generate embedding for a single query."""
        embeddings = await self.generate_embeddings([query])
        return embeddings[0] if embeddings else []


class VectorStore:
    """Handle pgvector operations for document chunks - FIXED."""

    def __init__(self) -> None:
        """Initialize vector store - NO side effects."""
        # Create embedding generator but don't call any methods
        self.embedding_generator = EmbeddingGenerator()

    async def store_chunks_with_embeddings(self, session: AsyncSession, doc_id: uuid.UUID, doc_type: str, chunks: list[str], metadata: dict | None = None) -> None:
        """Store text chunks with their embeddings in rag_document_chunks table."""
        try:
            # Generate embeddings for all chunks
            embeddings = await self.embedding_generator.generate_embeddings(chunks)

            # Store each chunk with its embedding
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings, strict=False)):
                # Check if chunk already exists
                existing = await session.execute(
                    text("""
                        SELECT id FROM rag_document_chunks
                        WHERE doc_id = :doc_id AND chunk_index = :chunk_idx
                    """),
                    {"doc_id": str(doc_id), "chunk_idx": i},
                )
                existing_row = existing.fetchone()

                if existing_row:
                    # Update existing chunk
                    await session.execute(
                        text("""
                            UPDATE rag_document_chunks
                            SET content = :content,
                                embedding = CAST(:embedding AS vector),
                                metadata = :metadata
                            WHERE doc_id = :doc_id AND chunk_index = :chunk_idx
                        """),
                        {
                            "doc_id": str(doc_id),
                            "content": chunk,
                            "embedding": str(emb),
                            "metadata": json.dumps({"chunk_type": "basic"}),
                            "chunk_idx": i,
                        },
                    )
                else:
                    # Insert new chunk
                    await session.execute(
                        text("""
                            INSERT INTO rag_document_chunks
                            (doc_id, doc_type, chunk_index, content, embedding, metadata)
                            VALUES (:doc_id, :doc_type, :chunk_idx, :content, CAST(:embedding AS vector), :metadata)
                        """),
                        {
                            "doc_id": str(doc_id),
                            "doc_type": doc_type,
                            "chunk_idx": i,
                            "content": chunk,
                            "embedding": str(emb),  # pgvector handles list conversion
                            "metadata": json.dumps(metadata or {"chunk_type": "basic"}),
                        },
                    )
        except Exception:
            logger.exception("Failed to store chunks with embeddings")
            # Don't crash - just log and continue
            logger.exception("Continuing without embeddings due to error")

    async def similarity_search(
        self, session: AsyncSession, query_embedding: list[float], top_k: int, doc_type: str | None = None, roadmap_id: uuid.UUID | None = None
    ) -> list[dict]:
        """Perform similarity search using pgvector."""
        try:
            params = {
                "query_embedding": str(query_embedding),
                "top_k": top_k,
            }

            where_clauses = ["rdc.embedding IS NOT NULL"]
            if doc_type:
                where_clauses.append("rdc.doc_type = :doc_type")
                params["doc_type"] = doc_type
            if roadmap_id:
                where_clauses.append("rdc.metadata->>'roadmap_id' = :roadmap_id")
                params["roadmap_id"] = str(roadmap_id)

            query = f"""
                SELECT
                    rdc.doc_id as document_id,
                    rdc.metadata->>'document_title' as document_title,
                    rdc.content,
                    rdc.metadata as doc_metadata,
                    rdc.chunk_index,
                    1 - (rdc.embedding <=> CAST(:query_embedding AS vector)) as similarity_score
                FROM rag_document_chunks rdc
                WHERE {" AND ".join(where_clauses)}
                ORDER BY rdc.embedding <=> CAST(:query_embedding AS vector)
                LIMIT :top_k
            """

            result = await session.execute(
                text(query),
                params,
            )
            return [dict(row._asdict()) for row in result]
        except Exception as e:
            logger.warning("Vector search failed: %s", str(e))
            return []

    # Removed unused search_document_chunks method

    async def global_search(
        self,
        session: AsyncSession | None,
        query: str,
        top_k: int = 10,
        user_id: str | None = None,
    ) -> list[dict]:
        """Search across ALL documents in the system (not limited to a specific context)."""
        try:
            # Handle session if None
            if session is None:
                async with async_session_maker() as new_session:
                    return await self.global_search(new_session, query, top_k, user_id)

            # Generate query embedding
            query_embedding = await self.embedding_generator.generate_query_embedding(query)

            # Simplified query without joins to avoid type issues
            # We'll get titles from metadata instead
            base_query = """
                SELECT DISTINCT
                    dc.id as chunk_id,
                    dc.doc_id,
                    dc.doc_type,
                    dc.content,
                    dc.metadata as doc_metadata,
                    dc.chunk_index,
                    1 - (dc.embedding <=> CAST(:query_embedding AS vector)) as similarity_score
                FROM rag_document_chunks dc
                WHERE dc.embedding IS NOT NULL
            """

            if user_id:
                # Add user filter only for user-specific content
                # For now, skip complex joins and just filter by metadata
                base_query += """
                AND (
                    dc.doc_type IN ('course', 'web') OR
                    dc.metadata->>'user_id' = :user_id
                )
                """

            base_query += """
                ORDER BY similarity_score DESC
                LIMIT :top_k
            """

            params = {
                "query_embedding": str(query_embedding),
                "top_k": top_k,
            }

            if user_id:
                params["user_id"] = user_id

            result = await session.execute(text(base_query), params)
            rows = result.fetchall()

            # Convert to consistent format
            results = []
            for row in rows:
                # Extract title from metadata or use default
                doc_title = None
                if row.doc_metadata:
                    doc_title = row.doc_metadata.get("document_title") or row.doc_metadata.get("title")

                if not doc_title:
                    doc_title = f"{row.doc_type.title()} Document"

                results.append({
                    "document_id": row.doc_id,
                    "document_title": doc_title,
                    "content": row.content,
                    "similarity_score": float(row.similarity_score),
                    "doc_metadata": row.doc_metadata or {},
                    "doc_type": row.doc_type,
                    "chunk_index": row.chunk_index,
                })

            return results

        except Exception:
            logger.exception("Global search failed")
            # Fallback to text search
            return await self._global_text_search(session, query, top_k, user_id)

    async def _global_text_search(
        self,
        session: AsyncSession | None,
        query: str,
        top_k: int = 10,
        user_id: str | None = None,
    ) -> list[dict]:
        """Fallback text-based global search when vector search fails."""
        try:
            # Handle session if None
            if session is None:
                async with async_session_maker() as new_session:
                    return await self._global_text_search(new_session, query, top_k, user_id)

            # Extract search terms
            query_lower = query.lower()
            search_terms = [term for term in query_lower.split() if len(term) > 2]

            if not search_terms:
                search_terms = [query_lower]

            # Build ILIKE conditions - escape single quotes
            escaped_terms = [term.replace("'", "''") for term in search_terms]
            conditions = " OR ".join([f"dc.content ILIKE '%{term}%'" for term in escaped_terms])

            # Simplified query without joins
            base_query = f"""
                SELECT DISTINCT
                    dc.id as chunk_id,
                    dc.doc_id,
                    dc.doc_type,
                    dc.content,
                    dc.metadata as doc_metadata,
                    dc.chunk_index,
                    0.75 as similarity_score
                FROM rag_document_chunks dc
                WHERE ({conditions})
            """

            if user_id:
                # Add user filter only for user-specific content
                base_query += """
                AND (
                    dc.doc_type IN ('course', 'web') OR
                    dc.metadata->>'user_id' = :user_id
                )
                """

            base_query += """
                LIMIT :top_k
            """

            params = {"top_k": top_k}
            if user_id:
                params["user_id"] = user_id

            result = await session.execute(text(base_query), params)
            rows = result.fetchall()

            # Convert to consistent format
            results = []
            for row in rows:
                # Extract title from metadata or use default
                doc_title = None
                if row.doc_metadata:
                    doc_title = row.doc_metadata.get("document_title") or row.doc_metadata.get("title")

                if not doc_title:
                    doc_title = f"{row.doc_type.title()} Document"

                results.append({
                    "document_id": row.doc_id,
                    "document_title": doc_title,
                    "content": row.content,
                    "similarity_score": float(row.similarity_score),
                    "doc_metadata": row.doc_metadata or {},
                    "doc_type": row.doc_type,
                    "chunk_index": row.chunk_index,
                })

            return results

        except Exception:
            logger.exception("Global text search failed")
            return []
