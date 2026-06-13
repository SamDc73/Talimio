"""RAG system service layer orchestrating LiteLLM + pgvector RAG flows."""


import asyncio
import logging
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import litellm
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from src.ai.client import LLMClient
from src.ai.errors import AIRuntimeError
from src.ai.prompts import (
    DIFFICULTY_AWARE_QUERY_TEMPLATE,
    MULTI_VIEW_QUERY_DECOMPOSITION_PROMPT,
    QUERY2DOC_EXPANSION_PROMPT,
    UTILITY_BATCH_FILTER_PROMPT,
)
from src.ai.rag.chunker import chunk_text_with_metadata_async
from src.ai.rag.config import get_rag_config
from src.ai.rag.embeddings import VectorRAG
from src.ai.rag.exceptions import (
    RagCourseNotFoundError,
    RagUnavailableError,
    RagValidationError,
)
from src.ai.rag.filters import deduplicate_by_similarity
from src.ai.rag.parser import DocumentProcessor
from src.ai.rag.schemas import MultiViewQueryExpansion, SearchResult, UtilityBatchFilterResponse
from src.books.models import Book
from src.courses.models import Course, CourseAttachment
from src.database.session import async_session_maker
from src.storage.exceptions import StorageError
from src.storage.factory import get_storage_provider
from src.videos.models import Video


logger = logging.getLogger(__name__)

CONTENT_TYPE_BOOK = "book"
CONTENT_TYPE_VIDEO = "video"
RAG_STATUS_PENDING = "pending"
RAG_STATUS_PROCESSING = "processing"
RAG_STATUS_COMPLETED = "completed"
RAG_STATUS_FAILED = "failed"
DEFAULT_SEARCH_TOP_K = 10
RERANK_CANDIDATE_MULTIPLIER = 4
LESSON_RETRIEVAL_CANDIDATE_TOP_K = 8
QUERY2DOC_MAX_WORDS = 20
MULTI_VIEW_MIN_WORDS = 5
LESSON_CONTEXT_TOP_K = 5
LEVEL_HINTS = {
    "beginner": "prefer introductory explanations, definitions, and worked examples with minimal assumed background.",
    "intermediate": "prefer applied explanations, comparisons, and common edge cases that deepen existing understanding.",
    "advanced": "prefer precise technical detail, tradeoffs, formal language, and non-obvious edge cases.",
}

_RERANK_RUNTIME_ERROR_TYPES = (
    TimeoutError,
    asyncio.TimeoutError,
    ConnectionError,
    OSError,
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
    litellm.RateLimitError,
    litellm.RouterRateLimitError,
    litellm.ServiceUnavailableError,
    litellm.Timeout,
    litellm.UnprocessableEntityError,
    litellm.UnsupportedParamsError,
)

_RAG_RUNTIME_ERROR_TYPES = (
    SQLAlchemyError,
    OSError,
    TimeoutError,
    asyncio.TimeoutError,
    ConnectionError,
    RagValidationError,
    RagUnavailableError,
)
_OPTIONAL_RETRIEVAL_LLM_ERROR_TYPES = (AIRuntimeError, TimeoutError, asyncio.TimeoutError, ConnectionError, OSError)


def _get_rerank_response_results(response: object) -> list[object]:
    raw_results = cast("dict[str, object]", response).get("results") if isinstance(response, dict) else getattr(response, "results", None)
    return cast("list[object]", raw_results) if isinstance(raw_results, list) else []


def _get_rerank_result_value(result: object, key: str) -> object:
    return cast("dict[str, object]", result).get(key) if isinstance(result, dict) else getattr(result, key, None)


def _log_rerank_fallback(
    *,
    rerank_model: str,
    candidates: list[SearchResult],
    top_k: int,
    latency_ms: float,
    reason: str,
    error_type: str | None = None,
) -> list[SearchResult]:
    fallback_results = candidates[:top_k]
    log_extra: dict[str, object] = {
        "rerank_model": rerank_model,
        "candidates_in": len(candidates),
        "results_out": len(fallback_results),
        "latency_ms": latency_ms,
        "reason": reason,
    }
    if error_type:
        log_extra["error_type"] = error_type

    logger.warning("rag.rerank.failed", extra=log_extra)
    logger.info(
        "rag.rerank",
        extra={
            "rerank_ran": True,
            "rerank_model": rerank_model,
            "candidates_in": len(candidates),
            "results_out": len(fallback_results),
            "latency_ms": latency_ms,
            "fallback_used": True,
        },
    )
    return fallback_results


class RAGService:
    """RAG service orchestrator built on LiteLLM embeddings and pgvector storage."""

    def __init__(self) -> None:
        """Initialize RAG service components for LiteLLM + pgvector pipeline."""
        self.config = get_rag_config()

        self._document_processor: DocumentProcessor | None = None
        self._vector_rag: VectorRAG | None = None

    @property
    def document_processor(self) -> DocumentProcessor:
        """Lazy load document processor."""
        if self._document_processor is None:
            self._document_processor = DocumentProcessor()
        return self._document_processor

    @property
    def vector_rag(self) -> VectorRAG:
        """Lazy load vector RAG."""
        if self._vector_rag is None:
            self._vector_rag = VectorRAG()
        return self._vector_rag

    async def _ensure_course_owned(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
    ) -> None:
        """Ensure the given course belongs to the specified user."""
        stmt = select(Course.id).where(Course.id == course_id, Course.user_id == user_id)
        result = await session.execute(stmt)
        if result.scalar_one_or_none() is None:
            raise RagCourseNotFoundError(course_id)

    async def _mark_book_failed_without_chunks(self, session: AsyncSession, book: Book, book_id: uuid.UUID) -> None:
        logger.warning("rag.book.no_text_chunks", extra={"book_id": str(book_id)})
        book.rag_status = RAG_STATUS_FAILED
        await session.flush()

    async def _validate_book_file(self, book: Book) -> bool:
        """Return True if the book has a valid, supported file. Set rag_status on failure."""
        if not getattr(book, "file_path", None):
            logger.warning("Book %s has no file path; marking as failed", book.id)
            book.rag_status = RAG_STATUS_FAILED
            return False

        file_type = (book.file_type or "").lower()
        if file_type not in {"pdf", "epub"}:
            logger.warning("Book %s has unsupported file type '%s'; marking as failed", book.id, file_type)
            book.rag_status = RAG_STATUS_FAILED
            return False

        return True

    async def _download_book_bytes(self, book: Book) -> bytes:
        storage = get_storage_provider(book.storage_provider)
        return await storage.download(book.file_path)

    async def _parse_book_to_text(self, book: Book, file_bytes: bytes) -> str:
        file_type = (book.file_type or "").lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_type}") as temp_file:
            temp_file.write(file_bytes)
            temp_path = temp_file.name
        try:
            return await self.document_processor.process_document(temp_path)
        finally:
            temp_file_path = Path(temp_path)
            try:
                await run_in_threadpool(temp_file_path.unlink)
            except OSError:
                logger.warning("rag.book.temp_cleanup_failed", extra={"book_id": str(book.id)}, exc_info=True)

    async def process_book(self, book_id: uuid.UUID) -> None:
        """Process one book in a dedicated RAG-owned session."""
        async with async_session_maker() as session:
            await self._process_book_in_session(session, book_id)

    async def _process_book_in_session(self, session: AsyncSession, book_id: uuid.UUID) -> None:
        """Process a book (parse, chunk, embed, index) with unified RAG pipeline."""
        try:
            # Load book
            book = await session.get(Book, book_id)
            if not book:
                logger.warning("Book %s not found for processing", book_id)
                await session.rollback()
                return

            if not await self._validate_book_file(book):
                await session.flush()
                await session.commit()
                return

            # Mark processing
            book.rag_status = RAG_STATUS_PROCESSING
            await session.flush()
            # Match the video path: persist status before slow storage,
            # parsing, and embedding work so no DB transaction stays open.
            await session.commit()

            file_bytes = await self._download_book_bytes(book)
            text_content = await self._parse_book_to_text(book, file_bytes)

            # Chunk
            chunks, per_chunk_metadata = await chunk_text_with_metadata_async(
                text_content,
                document_title=book.title or "",
                chunk_size=self.config.chunk_size,
                chunk_overlap_ratio=self.config.chunk_overlap_ratio,
            )
            if not self._has_valid_chunks(chunks):
                await self._mark_book_failed_without_chunks(session, book, book_id)
                await session.commit()
                return

            book = await session.get(Book, book_id)
            if not book:
                logger.info("Book %s was deleted before chunk storage started", book_id)
                await session.rollback()
                return

            # Store chunks
            await self.vector_rag.store_document_chunks_with_embeddings(
                session=session,
                doc_type=CONTENT_TYPE_BOOK,
                doc_id=book.id,
                title=book.title or "",
                chunks=chunks,
                per_chunk_metadata=per_chunk_metadata,
            )

            book = await session.get(Book, book_id)
            if not book:
                await self.delete_chunks_by_doc_id(session, book_id, doc_type=CONTENT_TYPE_BOOK)
                logger.info("Book %s was deleted during embedding; cleaned up chunks", book_id)
                await session.commit()
                return

            # Mark completed
            book.rag_status = RAG_STATUS_COMPLETED
            book.rag_processed_at = datetime.now(UTC)
            await session.flush()
            await session.commit()

            logger.info("Successfully processed book %s", book_id)

            # Note: We do not delete the original book file here; keep for user access

        except StaleDataError:
            # Book row was deleted between load and flush; treat as benign and exit quietly
            logger.info("Book %s was deleted during processing; aborting embedding", book_id)
            await session.rollback()
            return
        except (StorageError, *_RAG_RUNTIME_ERROR_TYPES):
            logger.exception("Failed to process book %s", book_id)
            # Best-effort mark failed
            try:
                await session.rollback()
                book = await session.get(Book, book_id)
                if book:
                    book.rag_status = RAG_STATUS_FAILED
                    await session.commit()
            except SQLAlchemyError:
                logger.debug("Failed to set book %s failed status after processing error", book_id, exc_info=True)
            raise

    async def ensure_attached_books_processed(self, session: AsyncSession, course_id: uuid.UUID) -> None:
        """Embed any attached books that have not completed RAG processing.

        This is the serialization point between attachment and grounding:
        Course generation calls it before building the grounding prompt, so
        newly attached pending books finish embedding off the request path.
        """
        book_ids = (
            (
                await session.execute(
                    select(CourseAttachment.book_id)
                    .join(Book, Book.id == CourseAttachment.book_id)
                    .where(
                        CourseAttachment.course_id == course_id,
                        Book.rag_status == RAG_STATUS_PENDING,
                    )
                )
            )
            .scalars()
            .all()
        )
        for book_id in book_ids:
            await self.process_book(book_id)

    async def process_video(self, video_id: uuid.UUID) -> None:
        """Process one video in a dedicated RAG-owned session."""
        async with async_session_maker() as session:
            await self._process_video_in_session(session, video_id)

    async def _process_video_in_session(self, session: AsyncSession, video_id: uuid.UUID) -> None:
        """Process a video (transcript segments to chunks → embed → index)."""
        try:
            video = await session.get(Video, video_id)
            if not video:
                logger.warning("Video %s not found for processing", video_id)
                return

            # Mark processing
            video.rag_status = RAG_STATUS_PROCESSING
            await session.flush()
            # Commit status before long-running embedding work to avoid holding row locks.
            await session.commit()

            video = await session.get(Video, video_id)
            if not video:
                logger.info("Video %s was deleted before transcript processing started", video_id)
                return

            # Collect transcript chunks
            chunks, per_chunk_meta = await self._collect_video_transcript_chunks(video)

            if not chunks:
                logger.warning("rag.video.no_transcript_chunks", extra={"video_id": str(video_id)})
                video.rag_status = RAG_STATUS_FAILED
                await session.flush()
                await session.commit()
                return

            await self.vector_rag.store_document_chunks_with_embeddings(
                session=session,
                doc_type=CONTENT_TYPE_VIDEO,
                doc_id=video.id,
                title=video.title or "",
                chunks=chunks,
                per_chunk_metadata=per_chunk_meta,
            )

            video = await session.get(Video, video_id)
            if not video:
                # Video was deleted while embedding; clean up any chunks written in this run.
                await self.delete_chunks_by_doc_id(session, video_id, doc_type=CONTENT_TYPE_VIDEO)
                await session.commit()
                return

            # Mark completed
            video.rag_status = RAG_STATUS_COMPLETED
            video.rag_processed_at = datetime.now(UTC)
            await session.flush()
            await session.commit()

            logger.info("Successfully processed video %s", video_id)

        except _RAG_RUNTIME_ERROR_TYPES:
            logger.exception("Failed to process video %s", video_id)
            try:
                await session.rollback()
                video = await session.get(Video, video_id)
                if video:
                    video.rag_status = RAG_STATUS_FAILED
                    await session.commit()
            except SQLAlchemyError:
                await session.rollback()
                logger.debug("Failed to set video %s failed status after processing error", video_id, exc_info=True)
            raise

    async def _collect_video_transcript_chunks(self, video: Video) -> tuple[list[str], list[dict]]:
        """Collect transcript chunks and per-chunk metadata for a video."""
        chunks: list[str] = []
        per_chunk_meta: list[dict] = []

        # Video transcripts stay segment-based so timestamp metadata remains exact.
        segments = None
        if getattr(video, "transcript_data", None) and isinstance(video.transcript_data, dict):
            segments = video.transcript_data.get("segments")

        if segments:
            for seg in segments:
                text_val = (seg.get("text") or "").strip()
                if not text_val:
                    continue
                chunks.append(text_val)
                per_chunk_meta.append({"start": seg.get("start"), "end": seg.get("end")})

        return chunks, per_chunk_meta

    @staticmethod
    def _has_valid_chunks(chunks: list[str]) -> bool:
        return any(chunk.strip() for chunk in chunks)

    async def search_documents(
        self, user_id: uuid.UUID, course_id: uuid.UUID, query: str, top_k: int | None = None
    ) -> list[SearchResult]:
        """Search documents scoped by user ownership."""
        try:
            async with async_session_maker() as session:
                await self._ensure_course_owned(session, user_id, course_id)
                candidates, effective_top_k, rerank_model = await self._load_course_document_candidates(
                    session=session,
                    course_id=course_id,
                    query=query,
                    top_k=top_k,
                )
                await session.commit()

            return await self._finalize_course_document_search(
                query=query,
                candidates=candidates,
                top_k=effective_top_k,
                rerank_model=rerank_model,
            )

        except _RAG_RUNTIME_ERROR_TYPES as error:
            logger.exception("Failed to search documents")
            message = "Failed to search documents"
            raise RagUnavailableError(message) from error

    async def search_course_documents(
        self, course_id: uuid.UUID, query: str, top_k: int | None = None
    ) -> list[SearchResult]:
        """Search book chunks reachable through the course's attachments."""
        try:
            async with async_session_maker() as session:
                candidates, effective_top_k, rerank_model = await self._load_course_document_candidates(
                    session=session,
                    course_id=course_id,
                    query=query,
                    top_k=top_k,
                )
                await session.commit()

            return await self._finalize_course_document_search(
                query=query,
                candidates=candidates,
                top_k=effective_top_k,
                rerank_model=rerank_model,
            )

        except _RAG_RUNTIME_ERROR_TYPES as error:
            logger.exception("Failed to search documents")
            message = "Failed to search documents"
            raise RagUnavailableError(message) from error

    async def search_lesson_documents(
        self,
        course_id: uuid.UUID,
        query: str,
        *,
        learner_level: str | None = None,
        top_k: int = LESSON_CONTEXT_TOP_K,
    ) -> list[SearchResult]:
        """Search course sources with lesson-specific query expansion and context packing."""
        async with async_session_maker() as session:
            has_searchable_chunks = await self._has_searchable_attached_book_chunks(session=session, course_id=course_id)
            await session.commit()
        if not has_searchable_chunks:
            return []

        retrieval_query = self._append_level_hint(query, learner_level=learner_level)
        retrieval_query = await self._expand_short_query(retrieval_query)

        if self._word_count(retrieval_query) < MULTI_VIEW_MIN_WORDS:
            results = await self.search_course_documents(
                course_id=course_id,
                query=retrieval_query,
                top_k=LESSON_RETRIEVAL_CANDIDATE_TOP_K,
            )
        else:
            results = await self._search_lesson_multi_view(
                course_id=course_id,
                query=retrieval_query,
                top_k=LESSON_RETRIEVAL_CANDIDATE_TOP_K,
            )

        deduped_results = deduplicate_by_similarity(results)
        filtered_results = await self._filter_results_by_utility(query=retrieval_query, results=deduped_results)
        return filtered_results[:top_k]

    async def _load_course_document_candidates(
        self,
        *,
        session: AsyncSession,
        course_id: uuid.UUID,
        query: str,
        top_k: int | None,
    ) -> tuple[list[SearchResult], int, str]:
        effective_top_k = top_k if top_k is not None else DEFAULT_SEARCH_TOP_K
        rerank_model = self.config.rerank_model.strip()
        search_limit = effective_top_k * RERANK_CANDIDATE_MULTIPLIER if rerank_model else effective_top_k
        candidates = await self.vector_rag.search(
            session=session,
            doc_type=CONTENT_TYPE_BOOK,
            query=query,
            limit=search_limit,
            course_id=course_id,
        )
        return candidates, effective_top_k, rerank_model

    async def _finalize_course_document_search(
        self,
        *,
        query: str,
        candidates: list[SearchResult],
        top_k: int,
        rerank_model: str,
    ) -> list[SearchResult]:
        if not rerank_model:
            logger.info(
                "rag.rerank",
                extra={
                    "rerank_ran": False,
                    "rerank_model": "",
                    "candidates_in": len(candidates),
                    "results_out": len(candidates),
                    "latency_ms": 0,
                },
            )
            return candidates
        return await self._rerank_candidates(
            query=query,
            candidates=candidates,
            top_k=top_k,
            rerank_model=rerank_model,
        )

    async def _has_searchable_attached_book_chunks(self, *, session: AsyncSession, course_id: uuid.UUID) -> bool:
        has_chunks = await session.scalar(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM course_attachments ca
                    JOIN rag_document_chunks chunk
                      ON chunk.doc_type = 'book' AND chunk.doc_id = ca.book_id
                    WHERE ca.course_id = CAST(:course_id AS uuid)
                    LIMIT 1
                )
                """,
            ),
            {"course_id": str(course_id)},
        )
        return bool(has_chunks)

    def _append_level_hint(self, query: str, *, learner_level: str | None) -> str:
        if learner_level is None:
            return query

        level_hint = LEVEL_HINTS.get(learner_level)
        if level_hint is None:
            return query
        return DIFFICULTY_AWARE_QUERY_TEMPLATE.format(query=query, level_hint=level_hint)

    async def _expand_short_query(self, query: str) -> str:
        if self._word_count(query) >= QUERY2DOC_MAX_WORDS:
            return query

        llm_client = LLMClient()
        try:
            response = await llm_client.get_completion(
                messages=[
                    {"role": "user", "content": QUERY2DOC_EXPANSION_PROMPT.format(query=query)},
                ],
                temperature=0.2,
                max_completion_tokens=220,
                enable_memory=False,
                enable_tools=False,
            )
        except _OPTIONAL_RETRIEVAL_LLM_ERROR_TYPES:
            logger.warning("rag.query2doc.failed", exc_info=True)
            return query

        if not isinstance(response, str) or not response.strip():
            return query
        return f"{query}\n{response.strip()}"

    async def _search_lesson_multi_view(
        self,
        *,
        course_id: uuid.UUID,
        query: str,
        top_k: int,
    ) -> list[SearchResult]:
        perspective_queries = await self._build_multi_view_queries(query)
        if not perspective_queries:
            return await self.search_course_documents(course_id=course_id, query=query, top_k=top_k)

        result_sets = await asyncio.gather(
            *(
                self.search_course_documents(
                    course_id=course_id,
                    query=perspective_query,
                    top_k=top_k,
                )
                for perspective_query in perspective_queries
            ),
            return_exceptions=True,
        )
        valid_result_sets: list[list[SearchResult]] = []
        for result_set in result_sets:
            if isinstance(result_set, _RAG_RUNTIME_ERROR_TYPES):
                logger.warning(
                    "rag.multi_view.search_failed",
                    exc_info=(type(result_set), result_set, result_set.__traceback__),
                )
                continue
            if isinstance(result_set, BaseException):
                raise result_set
            valid_result_sets.append(result_set)

        if not valid_result_sets:
            return await self.search_course_documents(course_id=course_id, query=query, top_k=top_k)
        return self._merge_results_with_rrf(valid_result_sets, top_k=top_k)

    async def _build_multi_view_queries(self, query: str) -> list[str]:
        llm_client = LLMClient()
        try:
            response = await llm_client.get_completion(
                messages=[
                    {"role": "user", "content": MULTI_VIEW_QUERY_DECOMPOSITION_PROMPT.format(query=query)},
                ],
                response_model=MultiViewQueryExpansion,
                temperature=0.1,
                max_completion_tokens=240,
                enable_memory=False,
                enable_tools=False,
            )
        except _OPTIONAL_RETRIEVAL_LLM_ERROR_TYPES:
            logger.warning("rag.multi_view.failed", exc_info=True)
            return []

        if not isinstance(response, MultiViewQueryExpansion):
            return []
        return [response.conceptual, response.practical, response.technical]

    def _merge_results_with_rrf(self, result_sets: list[list[SearchResult]], *, top_k: int) -> list[SearchResult]:
        by_chunk_id: dict[str, SearchResult] = {}
        scores: dict[str, float] = {}

        for results in result_sets:
            for rank, result in enumerate(results, start=1):
                by_chunk_id.setdefault(result.chunk_id, result)
                scores[result.chunk_id] = scores.get(result.chunk_id, 0.0) + self._rrf_score(rank)

        ranked_chunk_ids = sorted(scores, key=lambda chunk_id: scores[chunk_id], reverse=True)
        merged: list[SearchResult] = []
        for chunk_id in ranked_chunk_ids[:top_k]:
            result = by_chunk_id[chunk_id]
            merged.append(
                result.model_copy(
                    update={
                        "similarity_score": scores[chunk_id],
                        "metadata": {**result.metadata, "multi_view_rrf_score": scores[chunk_id]},
                    }
                )
            )
        return merged

    @staticmethod
    def _rrf_score(rank: int) -> float:
        return 1.0 / (60 + rank)

    async def _filter_results_by_utility(self, *, query: str, results: list[SearchResult]) -> list[SearchResult]:
        if len(results) <= LESSON_CONTEXT_TOP_K:
            return results

        chunks = "\n\n".join(f"[{index}]\n{result.content}" for index, result in enumerate(results))
        llm_client = LLMClient()
        try:
            response = await llm_client.get_completion(
                messages=[
                    {"role": "user", "content": UTILITY_BATCH_FILTER_PROMPT.format(query=query, chunks=chunks)},
                ],
                response_model=UtilityBatchFilterResponse,
                temperature=0.0,
                max_completion_tokens=160,
                enable_memory=False,
                enable_tools=False,
            )
        except _OPTIONAL_RETRIEVAL_LLM_ERROR_TYPES:
            logger.warning("rag.utility_filter.failed", exc_info=True)
            return results

        if not isinstance(response, UtilityBatchFilterResponse):
            return results

        useful_indices = [index for index in response.useful_indices if 0 <= index < len(results)]
        if not useful_indices:
            return results
        return [results[index] for index in useful_indices]

    @staticmethod
    def _word_count(text_value: str) -> int:
        return len(text_value.split())

    async def _rerank_candidates(
        self, *, query: str, candidates: list[SearchResult], top_k: int, rerank_model: str
    ) -> list[SearchResult]:
        """Rerank retrieved candidates with LiteLLM, falling back to retrieval order if unavailable."""
        started_at = time.perf_counter()
        try:
            response = await litellm.arerank(
                model=rerank_model,
                query=query,
                documents=[candidate.content for candidate in candidates],
                top_n=top_k,
            )
        except _RERANK_RUNTIME_ERROR_TYPES as error:
            latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
            return _log_rerank_fallback(
                rerank_model=rerank_model,
                candidates=candidates,
                top_k=top_k,
                latency_ms=latency_ms,
                reason="provider_error",
                error_type=type(error).__name__,
            )

        reranked: list[SearchResult] = []
        for result in _get_rerank_response_results(response):
            index = _get_rerank_result_value(result, "index")
            relevance_score = _get_rerank_result_value(result, "relevance_score")
            if not isinstance(index, int) or not isinstance(relevance_score, int | float):
                continue
            if index < 0 or index >= len(candidates):
                continue

            candidate = candidates[index]
            reranked.append(
                candidate.model_copy(
                    update={
                        "similarity_score": float(relevance_score),
                        "metadata": {
                            **candidate.metadata,
                            "retrieval_score": candidate.similarity_score,
                            "rerank_score": float(relevance_score),
                        },
                    }
                )
            )

        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        if not reranked and candidates:
            return _log_rerank_fallback(
                rerank_model=rerank_model,
                candidates=candidates,
                top_k=top_k,
                latency_ms=latency_ms,
                reason="malformed_response",
            )

        logger.info(
            "rag.rerank",
            extra={
                "rerank_ran": True,
                "rerank_model": rerank_model,
                "candidates_in": len(candidates),
                "results_out": len(reranked),
                "latency_ms": latency_ms,
                "fallback_used": False,
            },
        )
        return reranked

    @staticmethod
    async def delete_chunks_by_doc_id(
        session: AsyncSession,
        document_id: uuid.UUID,
        doc_type: str,
    ) -> int:
        """Delete all RAG chunks owned by one book or video row.

        Returns the number of chunks deleted.
        """
        import time

        start_time = time.time()

        try:
            result = await session.execute(
                text("DELETE FROM rag_document_chunks WHERE doc_id = :doc_id AND doc_type = :doc_type"),
                {"doc_id": document_id, "doc_type": doc_type},
            )

            await session.flush()
            rowcount = int(getattr(result, "rowcount", 0) or 0)

            elapsed_time = time.time() - start_time
            logger.info(
                "Deleted %s RAG chunks for %s document %s in %.2f seconds",
                rowcount,
                doc_type,
                document_id,
                elapsed_time,
            )

            return rowcount

        except SQLAlchemyError:
            logger.exception("Error deleting RAG chunks for document %s", document_id)
            # Don't raise - this is best-effort cleanup
            return 0

    @staticmethod
    async def purge_for_content(
        session: AsyncSession,
        content_type: str,
        content_id: uuid.UUID,
    ) -> int:
        """Unified RAG purge entrypoint for content delete.

        - book: delete by doc_id + doc_type='book'
        - video: delete by doc_id + doc_type='video'
        - course: nothing to purge — courses own no chunks; attachments
          cascade at the SQL layer and books always keep their embeddings.
        Returns number of chunks deleted (best-effort).
        """
        try:
            t = content_type.lower()
            if t == CONTENT_TYPE_BOOK:
                return await RAGService.delete_chunks_by_doc_id(session, content_id, doc_type=CONTENT_TYPE_BOOK)
            if t == CONTENT_TYPE_VIDEO:
                return await RAGService.delete_chunks_by_doc_id(session, content_id, doc_type=CONTENT_TYPE_VIDEO)
            return 0
        except SQLAlchemyError:
            logger.exception("RAG purge failed for %s %s", content_type, content_id)
            return 0
