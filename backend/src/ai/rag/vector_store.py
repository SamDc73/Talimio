"""Vector store operations and embedding generation."""

import uuid

from litellm import embedding
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.constants import rag_config


class EmbeddingGenerator:
    """Generate embeddings using LiteLLM."""

    def __init__(self) -> None:
        """Initialize embedding generator with configuration."""
        self.model = rag_config.embedding_model
        self.dimensions = rag_config.embedding_dim
        self.instruction = rag_config.embed_instruction

    async def generate_embeddings(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        """Generate embeddings for text chunks."""
        # Add instruction prefix for queries only (not documents)
        prefixed_texts = [f"{self.instruction} {text}" for text in texts] if is_query else texts

        # Generate embeddings using LiteLLM
        response = embedding(model=self.model, input=prefixed_texts, dimensions=self.dimensions)

        return [item["embedding"] for item in response["data"]]

    async def generate_query_embedding(self, query: str) -> list[float]:
        """Generate embedding for a single query."""
        embeddings = await self.generate_embeddings([query], is_query=True)
        return embeddings[0]


class VectorStore:
    """Handle pgvector operations for document chunks."""

    def __init__(self) -> None:
        """Initialize vector store."""
        self.embedding_generator = EmbeddingGenerator()

    async def store_chunks_with_embeddings(self, session: AsyncSession, document_id: int, chunks: list[str]) -> None:
        """Store text chunks with their embeddings in pgvector."""
        # Generate embeddings for all chunks
        embeddings = await self.embedding_generator.generate_embeddings(chunks)

        # Store each chunk with its embedding
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings, strict=False)):
            node_id = f"doc_{document_id}_chunk_{i}"

            # Insert chunk with embedding using raw SQL for vector column
            await session.execute(
                text("""
                    INSERT INTO document_chunks
                    (document_id, node_id, chunk_index, content, embedding, token_count)
                    VALUES (:doc_id, :node_id, :chunk_idx, :content, :embedding, :tokens)
                """),
                {
                    "doc_id": document_id,
                    "node_id": node_id,
                    "chunk_idx": i,
                    "content": chunk,
                    "embedding": str(emb),  # pgvector handles list conversion
                    "tokens": len(chunk.split()),
                },
            )

        await session.commit()

    async def delete_document_chunks(self, session: AsyncSession, document_id: int) -> None:
        """Delete all chunks for a document."""
        await session.execute(text("DELETE FROM document_chunks WHERE document_id = :doc_id"), {"doc_id": document_id})
        await session.commit()

    async def similarity_search(
        self, session: AsyncSession, query_embedding: list[float], roadmap_id: uuid.UUID, top_k: int
    ) -> list[dict]:
        """Perform similarity search using pgvector."""
        result = await session.execute(
            text("""
                SELECT
                    dc.document_id,
                    rd.title as document_title,
                    dc.content,
                    dc.doc_metadata,
                    1 - (dc.embedding <=> :query_embedding) as similarity_score
                FROM document_chunks dc
                JOIN roadmap_documents rd ON dc.document_id = rd.id
                WHERE rd.roadmap_id = :roadmap_id
                AND rd.status = 'embedded'
                ORDER BY dc.embedding <=> :query_embedding
                LIMIT :top_k
            """),
            {"query_embedding": str(query_embedding), "roadmap_id": str(roadmap_id), "top_k": top_k},
        )

        return [
            {
                "document_id": row.document_id,
                "document_title": row.document_title,
                "content": row.content,
                "doc_metadata": row.doc_metadata,
                "similarity_score": row.similarity_score,
            }
            for row in result.fetchall()
        ]
