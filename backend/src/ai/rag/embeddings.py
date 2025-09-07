"""Vector-based RAG implementation using LiteLLM embeddings and pgvector."""

import json
import logging
import os
import uuid

import litellm
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.rag.schemas import SearchResult


logger = logging.getLogger(__name__)


class VectorRAG:
    """Vector-based RAG using LiteLLM embeddings and pgvector."""

    def __init__(self) -> None:
        """Initialize with embedding model from environment."""
        self.embedding_model = os.getenv("RAG_EMBEDDING_MODEL")
        if not self.embedding_model:
            error_msg = "RAG_EMBEDDING_MODEL environment variable not set"
            raise ValueError(error_msg)
        
        # Get embedding dimension if specified
        # LiteLLM will handle dropping this param for models that don't support it
        self.embedding_dim = os.getenv("RAG_EMBEDDING_OUTPUT_DIM")
        if self.embedding_dim:
            self.embedding_dim = int(self.embedding_dim)
        
        logger.info(f"VectorRAG initialized with model: {self.embedding_model}, dim: {self.embedding_dim}")

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for text using LiteLLM's async support."""
        try:
            # Build kwargs for LiteLLM
            embed_kwargs = {
                "model": self.embedding_model,
                "input": [text],
                "timeout": 30,  # Reasonable timeout
                "num_retries": 2,  # Retry on failure
            }
            
            # Pass dimensions if specified - LiteLLM will drop it for unsupported models
            # when LITELLM_DROP_PARAMS=true (which we have set)
            if self.embedding_dim:
                embed_kwargs["dimensions"] = self.embedding_dim
            
            # Use LiteLLM's async embedding - provider agnostic
            response = await litellm.aembedding(**embed_kwargs)

            # Handle the response structure
            if hasattr(response, "data") and response.data:
                embedding = response.data[0].get("embedding", response.data[0])
            else:
                # Direct embedding response
                embedding = response

            # Validate embedding
            if not embedding or not isinstance(embedding, (list, tuple)):
                error_msg = f"Invalid embedding response: {type(embedding)}"
                raise ValueError(error_msg)

            logger.debug(f"Generated embedding of dimension {len(embedding)}")
            return embedding

        except Exception as e:
            error_msg = f"Failed to generate embedding: {e}"
            logger.exception(error_msg)
            raise

    async def store_document_chunks_with_embeddings(
        self,
        session: AsyncSession,
        document_id: int,
        course_id: uuid.UUID,
        title: str,
        chunks: list[str]
    ) -> None:
        """Store document chunks with their embeddings in pgvector."""
        try:
            # Generate a deterministic doc_id based on document_id
            doc_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, f"document_{document_id}")

            # Process each chunk
            for i, chunk_text in enumerate(chunks):
                if not chunk_text.strip():
                    continue

                # Generate embedding for the chunk
                logger.info(f"Generating embedding for chunk {i}/{len(chunks)}")
                embedding = await self.generate_embedding(chunk_text)

                # Create metadata
                metadata = {
                    "course_id": str(course_id),
                    "document_id": document_id,
                    "title": title,
                    "chunk_index": i,
                    "total_chunks": len(chunks)
                }

                # Convert embedding to pgvector format
                embedding_str = f"[{','.join(map(str, embedding))}]"

                # Insert chunk with embedding into database
                await session.execute(
                    text("""
                        INSERT INTO rag_document_chunks
                        (doc_id, doc_type, chunk_index, content, metadata, embedding, created_at)
                        VALUES (:doc_id, :doc_type, :chunk_index, :content, CAST(:metadata AS jsonb),
                                CAST(:embedding AS vector), NOW())
                        ON CONFLICT (doc_id, chunk_index)
                        DO UPDATE SET
                            content = EXCLUDED.content,
                            metadata = EXCLUDED.metadata,
                            embedding = EXCLUDED.embedding
                    """),
                    {
                        "doc_id": doc_uuid,
                        "doc_type": "course",
                        "chunk_index": i,
                        "content": chunk_text,
                        "metadata": json.dumps(metadata),
                        "embedding": embedding_str
                    }
                )

            await session.commit()
            logger.info(f"Stored {len(chunks)} chunks with embeddings for document {document_id}")

        except Exception:
            logger.exception("Failed to store chunks with embeddings")
            await session.rollback()
            raise

    async def search_course_documents_vector(
        self,
        session: AsyncSession,
        course_id: uuid.UUID,
        query: str,
        limit: int = 5
    ) -> list[SearchResult]:
        """Search course documents using vector similarity."""
        try:
            # Generate embedding for the query
            logger.info(f"Generating embedding for query: {query}")
            query_embedding = await self.generate_embedding(query)


            # Convert to pgvector format
            embedding_str = f"[{','.join(map(str, query_embedding))}]"

            # Search using pgvector similarity (L2 distance)
            result = await session.execute(
                text("""
                    SELECT
                        doc_id,
                        chunk_index,
                        content,
                        metadata,
                        1 - (embedding <-> CAST(:query_embedding AS vector)) as similarity
                    FROM rag_document_chunks
                    WHERE doc_type = 'course'
                    AND metadata->>'course_id' = :course_id
                    AND embedding IS NOT NULL
                    ORDER BY embedding <-> CAST(:query_embedding AS vector)
                    LIMIT :limit
                """),
                {
                    "course_id": str(course_id),
                    "query_embedding": embedding_str,
                    "limit": limit
                }
            )

            rows = result.fetchall()

            # Convert to SearchResult format
            results = [
                SearchResult(
                    chunk_id=f"{row.doc_id}_{row.chunk_index}",
                    content=row.content,
                    similarity_score=row.similarity if row.similarity > 0 else 0.1,
                    metadata=row.metadata or {}
                )
                for row in rows
            ]

            logger.info(f"Found {len(results)} vector search results for query: {query}")
            return results

        except Exception:
            logger.exception("Vector search failed")
            return []

    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
        """Chunk text with overlap for better context preservation."""
        words = text.split()
        chunks = []

        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)

        return chunks
