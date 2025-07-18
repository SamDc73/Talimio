"""Document retrieval and search components."""

import logging
import uuid
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.constants import rag_config
from src.ai.rag.schemas import SearchResult as BaseSearchResult
from src.ai.rag.vector_store import VectorStore
from src.database.session import async_session_maker


# Removed unused CrossEncoder import


logger = logging.getLogger(__name__)


class Reranker:
    """Optional reranking component for quality boost."""

    def __init__(self) -> None:
        """Initialize reranker with configuration."""
        self.model = rag_config.rerank_model
        self.enabled = rag_config.rerank_enabled

    async def rerank_results(self, query: str, candidates: list[dict], top_k: int) -> list[dict]:
        """Rerank candidates using Qwen 3 reranker."""
        if not self.enabled or len(candidates) <= top_k:
            return candidates[:top_k]

        # TODO: Implement Qwen 3 reranker in future enhancement
        # For now, return top candidates by similarity score
        sorted_candidates = sorted(candidates, key=lambda x: x["similarity_score"], reverse=True)

        return sorted_candidates[:top_k]


# Removed unused CrossEncoderReranker class


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
    ) -> list[BaseSearchResult]:
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

        # Convert to BaseSearchResult objects
        results = []
        for candidate in candidates:
            result = BaseSearchResult(
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


class ContextAwareRetriever:
    """Context-aware retrieval for assistant chat with document/resource context."""

    def __init__(self) -> None:
        self.document_retriever = DocumentRetriever()
        self.vector_store = VectorStore()

    async def retrieve_context(
        self,
        query: str,
        context_type: str,
        context_id: UUID,
        context_meta: dict[str, Any] | None = None,
        max_chunks: int | None = None,
        relevance_threshold: float | None = None,
    ) -> list[BaseSearchResult]:
        """Retrieve relevant context for a query within a specific document/resource."""
        logger.debug(
            'ContextAwareRetriever.retrieve_context called with context_type=%s, context_id=%s, query="%s", max_chunks=%s, relevance_threshold=%s',
            context_type,
            context_id,
            query,
            max_chunks,
            relevance_threshold,
        )
        method = "course" if context_type == "course" else "vector"
        logger.debug("ContextAwareRetriever.retrieve_context: selected retrieval method=%s", method)
        # For course context, use the document retriever to search across all course documents
        if context_type == "course":
            async with async_session_maker() as session:
                try:
                    # Use document retriever for semantic search
                    results = await self.document_retriever.search_documents(
                        session=session,
                        roadmap_id=context_id,  # context_id is the course/roadmap ID
                        query=query,
                        top_k=max_chunks or 5,
                    )
                    logger.debug(
                        "ContextAwareRetriever.retrieve_context: method=course, context_type=%s, context_id=%s, returned=%d results",
                        context_type,
                        context_id,
                        len(results),
                    )
                    return results
                except Exception:
                    logger.exception("Failed to retrieve course documents:")
                    return []

        # For other context types (book, video, etc.), use document-specific search
        # Map context type to doc type
        doc_type_mapping = {
            "book": "book",
            "video": "video",
            "article": "article",
            "web": "web",
            "lesson": "lesson",
            "roadmap": "roadmap",
            "flashcard": "flashcard",
            "tag": "tag",
        }

        doc_type = doc_type_mapping.get(context_type, context_type)
        logger.debug(
            "Retrieving '%s' context via vector store: context_type=%s, context_id=%s, top_k=%s",
            doc_type,
            context_type,
            context_id,
            max_chunks or 10,
        )

        async with async_session_maker() as session:
            try:
                query_embedding = await self.vector_store.embedding_generator.generate_query_embedding(query)
                logger.debug(
                    "Generated query embedding length=%d for context_type=%s, context_id=%s",
                    len(query_embedding),
                    context_type,
                    context_id,
                )
                # Search for chunks based on the context
                candidates = await self.vector_store.similarity_search(
                    session=session,
                    query_embedding=query_embedding,
                    top_k=max_chunks or 10,
                    doc_type=doc_type,
                )
                logger.debug(
                    "Vector store similarity_search returned %d candidates for doc_type=%s, context_type=%s, context_id=%s",
                    len(candidates),
                    doc_type,
                    context_type,
                    context_id,
                )
                results = self._to_search_results(candidates)
                logger.debug(
                    "ContextAwareRetriever.retrieve_context: method=vector, context_type=%s, context_id=%s, doc_type=%s, returned=%d results",
                    context_type,
                    context_id,
                    doc_type,
                    len(results),
                )

            except Exception:
                logger.exception("Failed to retrieve document chunks:")
                results = []

        # Convert dict results to BaseSearchResult objects
        search_results = []
        for result in results:
            if isinstance(result, dict):
                search_results.append(
                    BaseSearchResult(
                        document_id=result["document_id"],
                        document_title=result["document_title"],
                        chunk_content=result["content"],
                        similarity_score=result["similarity_score"],
                        doc_metadata=result.get("doc_metadata", {}),
                    )
                )
            else:
                search_results.append(result)

        # Post-process for context-aware scoring
        if context_meta:
            search_results = self._apply_context_aware_scoring(search_results, context_meta)

        return search_results

    def _apply_context_aware_scoring(
        self, results: list[BaseSearchResult], context_meta: dict[str, Any]
    ) -> list[BaseSearchResult]:
        """Apply context-aware scoring based on proximity to current context."""
        for result in results:
            boost = 1.0

            # Page proximity boost for books/documents
            if "page" in context_meta and "page" in result.metadata:
                current_page = context_meta["page"]
                result_page = result.metadata["page"]
                page_distance = abs(current_page - result_page)

                # Boost based on proximity (exponential decay)
                if page_distance == 0:
                    boost *= 1.5  # Same page
                elif page_distance <= 2:
                    boost *= 1.3  # Very close
                elif page_distance <= 5:
                    boost *= 1.1  # Close
                elif page_distance <= 10:
                    boost *= 1.05  # Nearby

            # Timestamp proximity boost for videos
            if "timestamp" in context_meta and "start_time" in result.metadata:
                current_time = context_meta["timestamp"]
                chunk_start = result.metadata["start_time"]
                chunk_end = result.metadata.get("end_time", chunk_start + 60)

                # Check if current time is within chunk
                if chunk_start <= current_time <= chunk_end:
                    boost *= 1.5  # Currently playing chunk
                else:
                    # Boost based on temporal proximity
                    time_distance = min(abs(current_time - chunk_start), abs(current_time - chunk_end))
                    if time_distance <= 30:
                        boost *= 1.3  # Very close
                    elif time_distance <= 60:
                        boost *= 1.1  # Close
                    elif time_distance <= 120:
                        boost *= 1.05  # Nearby

            # Apply boost to final score
            if result.final_score:
                result.final_score *= boost
            else:
                result.final_score = result.similarity_score * boost

        # Re-sort by boosted scores
        results.sort(key=lambda x: x.final_score or 0, reverse=True)
        return results

    def _to_search_results(self, candidates: list[dict]) -> list[BaseSearchResult]:
        """Convert a list of candidate dicts to a list of BaseSearchResult objects."""
        results = []
        for candidate in candidates:
            result = BaseSearchResult(
                document_id=candidate["document_id"],
                document_title=candidate["document_title"],
                chunk_content=candidate["content"],
                similarity_score=candidate["similarity_score"],
                doc_metadata=candidate["doc_metadata"],
            )
            results.append(result)
        return results


    async def global_retrieve(
        self,
        query: str,
        user_id: str | None = None,
        max_chunks: int = 10,
        relevance_threshold: float = 0.4,
    ) -> list[BaseSearchResult]:
        """Retrieve relevant content from ALL documents (not limited to a specific context)."""
        async with async_session_maker() as session:
            try:
                # Use vector store's global search
                results = await self.vector_store.global_search(
                    session=session,
                    query=query,
                    top_k=max_chunks,
                    user_id=user_id,
                )

                return [
                    BaseSearchResult(
                        document_id=result["document_id"],
                        document_title=result["document_title"],
                        chunk_content=result["content"],
                        similarity_score=result["similarity_score"],
                        doc_metadata={
                            **result.get("doc_metadata", {}),
                            "doc_type": result["doc_type"],
                            "chunk_index": result["chunk_index"],
                        },
                    )
                    for result in results
                    if result["similarity_score"] >= relevance_threshold
                ]

            except Exception:
                logger.exception("Failed to retrieve global content:")
                return []
