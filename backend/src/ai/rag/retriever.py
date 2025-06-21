"""Document retrieval and search components."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.constants import rag_config
from src.ai.rag.schemas import SearchResult
from src.ai.rag.vector_store import VectorStore


class Reranker:
    """Optional reranking component for quality boost."""

    def __init__(self) -> None:
        """Initialize reranker with configuration."""
        self.model = rag_config.rerank_model
        self.enabled = rag_config.rerank_enabled

    async def rerank_results(self, query: str, candidates: list[dict], top_k: int) -> list[dict]:  # noqa: ARG002
        """Rerank candidates using Qwen 3 reranker."""
        if not self.enabled or len(candidates) <= top_k:
            return candidates[:top_k]

        # TODO: Implement Qwen 3 reranker in future enhancement
        # For now, return top candidates by similarity score
        sorted_candidates = sorted(candidates, key=lambda x: x["similarity_score"], reverse=True)

        return sorted_candidates[:top_k]


class DocumentRetriever:
    """Coordinate document search and retrieval pipeline."""

    def __init__(self) -> None:
        """Initialize retriever with components."""
        self.vector_store = VectorStore()
        self.reranker = Reranker()
        self.top_k = rag_config.top_k
        self.rerank_k = rag_config.rerank_k

    async def search_documents(
        self, session: AsyncSession, roadmap_id: uuid.UUID, query: str, top_k: int | None = None
    ) -> list[SearchResult]:
        """Search documents using vector similarity with optional reranking."""
        if top_k is None:
            top_k = self.rerank_k

        # Stage 1: Generate query embedding
        query_embedding = await self.vector_store.embedding_generator.generate_query_embedding(query)

        # Stage 2: Vector similarity search (get more candidates for reranking)
        search_top_k = self.top_k if self.reranker.enabled else top_k
        candidates = await self.vector_store.similarity_search(
            session=session, query_embedding=query_embedding, roadmap_id=roadmap_id, top_k=search_top_k
        )

        # Stage 3: Optional reranking
        if self.reranker.enabled and len(candidates) > top_k:
            candidates = await self.reranker.rerank_results(query, candidates, top_k)
        else:
            candidates = candidates[:top_k]

        # Convert to SearchResult objects
        results = []
        for candidate in candidates:
            result = SearchResult(
                document_id=candidate["document_id"],
                document_title=candidate["document_title"],
                chunk_content=candidate["content"],
                similarity_score=candidate["similarity_score"],
                doc_metadata=candidate["doc_metadata"],
            )
            results.append(result)

        return results

    async def get_document_context(
        self, session: AsyncSession, roadmap_id: uuid.UUID, query: str, max_chunks: int = 5
    ) -> str:
        """Get relevant document context for AI generation tasks."""
        results = await self.search_documents(session=session, roadmap_id=roadmap_id, query=query, top_k=max_chunks)

        if not results:
            return ""

        # Combine chunks into context with source attribution
        context_parts = [f"[Source: {result.document_title}]\n{result.chunk_content}\n" for result in results]

        return "\n".join(context_parts)
