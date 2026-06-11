"""Hybrid retrieval over pedagogical notes (dense pgvector + lexical FTS).

Mirrors the RAG retrieval shape (src/ai/rag/embeddings.py) without touching it:
both legs over-fetch limit*4 candidates, RRF-fuse with k=60, then an optional
litellm rerank reorders the survivors with graceful fallback to fused order.
The search abstains (returns []) instead of padding weak results, and a failed
query embedding degrades to lexical-only rather than raising to the tool.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, cast

import litellm


if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.engine import RowMapping
    from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import text

from src.ai.rag.exceptions import RagUnavailableError


logger = logging.getLogger(__name__)

# Same fusion constants as the RAG hybrid search; its helper is a VectorRAG
# method over chunk rows, so the 1/(k+rank) sum is restated here instead of
# refactoring that module.
_RRF_K = 60
_HYBRID_CANDIDATE_MULTIPLIER = 4

# Abstain floors. Exact KNN always returns *something*, so weak results must be
# dropped rather than padded:
# - _DENSE_SCORE_FLOOR: dense candidates below this cosine similarity never
#   enter fusion (an unrelated query is near-orthogonal to every note).
# - Single-leg rule: a fused hit survives only when BOTH legs agree, or when a
#   single-leg hit has RRF score >= 1/(_RRF_K + 2*limit) — i.e. it ranks within
#   the top 2*limit of its own leg.
# - _RERANK_SCORE_FLOOR: when rerank relevance scores are available they are
#   the better signal; hits below this floor are dropped.
_DENSE_SCORE_FLOOR = 0.30
_RERANK_SCORE_FLOOR = 0.30

# Errors that downgrade a leg or the rerank instead of failing the search;
# mirrors the runtime error tuples in src/ai/rag/{embeddings,service}.py.
EMBEDDING_FAILURE_ERROR_TYPES = (
    TimeoutError,
    asyncio.TimeoutError,
    ConnectionError,
    OSError,
    litellm.Timeout,
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
    litellm.UnprocessableEntityError,
    litellm.UnsupportedParamsError,
)


@dataclass(slots=True)
class NoteHit:
    """One retrieved pedagogical note with provenance and a relevance score."""

    note: str
    scene_trace: str
    occurred_at: datetime
    source_kind: str
    source_id: uuid.UUID | None
    score: float


@dataclass(slots=True)
class _FusedNote:
    hit: NoteHit
    fused_score: float = 0.0
    in_dense: bool = False
    in_lexical: bool = False


_DENSE_SEARCH_SQL = """
    SELECT id, note, scene_trace, occurred_at, source_kind, source_id,
           1 - (embedding <=> CAST(:query_embedding AS vector)) AS dense_score
    FROM pedagogical_notes
    WHERE __NOTE_SCOPE__
      AND embedding IS NOT NULL
    ORDER BY embedding <=> CAST(:query_embedding AS vector)
    LIMIT :candidate_limit
"""

# plainto_tsquery with the language-agnostic 'simple' config (no stemming or
# stopwords), matching the document-side tsvector. The quote is concatenated
# first so raw learner phrasing carries the lexical ranking.
_LEXICAL_SEARCH_SQL = """
    SELECT id, note, scene_trace, occurred_at, source_kind, source_id,
           ts_rank(
               to_tsvector('simple', verbatim_quote || ' ' || note),
               plainto_tsquery('simple', :query)
           ) AS lexical_score
    FROM pedagogical_notes
    WHERE __NOTE_SCOPE__
      AND to_tsvector('simple', verbatim_quote || ' ' || note) @@ plainto_tsquery('simple', :query)
    ORDER BY lexical_score DESC, occurred_at DESC
    LIMIT :candidate_limit
"""


async def search_learner_notes(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    query: str,
    course_id: uuid.UUID | None = None,
    limit: int = 5,
) -> list[NoteHit]:
    """Hybrid-search the learner's pedagogical notes; abstains rather than pads."""
    query_text = query.strip()
    if not query_text or limit <= 0:
        return []

    scope_sql, params = _build_note_scope(user_id=user_id, course_id=course_id)
    params["query"] = query_text
    params["candidate_limit"] = limit * _HYBRID_CANDIDATE_MULTIPLIER

    dense_rows: list[RowMapping] = []
    try:
        query_embedding = await _generate_query_embedding(query_text)
    except (RagUnavailableError, *EMBEDDING_FAILURE_ERROR_TYPES):
        logger.warning("memory.notes_search.query_embedding_failed", exc_info=True)
        query_embedding = None

    if query_embedding is not None:
        dense_params = {**params, "query_embedding": _format_vector(query_embedding)}
        dense_result = await session.execute(text(_DENSE_SEARCH_SQL.replace("__NOTE_SCOPE__", scope_sql)), dense_params)
        dense_rows = [row for row in dense_result.mappings().all() if float(row["dense_score"]) >= _DENSE_SCORE_FLOOR]

    lexical_result = await session.execute(text(_LEXICAL_SEARCH_SQL.replace("__NOTE_SCOPE__", scope_sql)), params)
    lexical_rows = lexical_result.mappings().all()

    fused = _fuse_note_rows(dense_rows, lexical_rows)
    survivors = [item for item in fused if _passes_abstain_floor(item, limit=limit)]
    survivors.sort(key=lambda item: item.fused_score, reverse=True)

    for item in survivors:
        item.hit.score = item.fused_score

    hits = [item.hit for item in survivors]
    reranked = await _rerank_note_hits(query=query_text, hits=hits, limit=limit)
    if reranked is not None:
        return reranked
    return hits[:limit]


async def _generate_query_embedding(query_text: str) -> list[float] | None:
    """Embed the search query via the shared RAG embedding model."""
    from src.ai.rag.embeddings import VectorRAG

    return await VectorRAG().generate_embedding(query_text)


def _build_note_scope(*, user_id: uuid.UUID, course_id: uuid.UUID | None) -> tuple[str, dict[str, object]]:
    predicates = ["user_id = :user_id", "deleted_at IS NULL"]
    params: dict[str, object] = {"user_id": user_id}
    if course_id is not None:
        # Course-scoped searches still include user-level notes (course_id IS
        # NULL): a global fact about the learner applies in every course.
        predicates.append("(course_id = :course_id OR course_id IS NULL)")
        params["course_id"] = course_id
    return " AND ".join(predicates), params


def _fuse_note_rows(dense_rows: Sequence[RowMapping], lexical_rows: Sequence[RowMapping]) -> list[_FusedNote]:
    """Sum 1/(k+rank) per leg, exactly like the RAG hybrid fusion."""
    fused: dict[uuid.UUID, _FusedNote] = {}

    for rank, row in enumerate(dense_rows, start=1):
        item = fused.setdefault(row["id"], _FusedNote(hit=_row_to_hit(row)))
        item.in_dense = True
        item.fused_score += 1.0 / (_RRF_K + rank)

    for rank, row in enumerate(lexical_rows, start=1):
        item = fused.setdefault(row["id"], _FusedNote(hit=_row_to_hit(row)))
        item.in_lexical = True
        item.fused_score += 1.0 / (_RRF_K + rank)

    return list(fused.values())


def _passes_abstain_floor(item: _FusedNote, *, limit: int) -> bool:
    if item.in_dense and item.in_lexical:
        return True
    return item.fused_score >= 1.0 / (_RRF_K + 2 * limit)


def _row_to_hit(row: RowMapping) -> NoteHit:
    return NoteHit(
        note=str(row["note"]),
        scene_trace=str(row["scene_trace"]),
        occurred_at=row["occurred_at"],
        source_kind=str(row["source_kind"]),
        source_id=row["source_id"],
        score=0.0,
    )


def _resolve_rerank_model() -> str:
    from src.ai.rag.config import get_rag_config

    return get_rag_config().rerank_model.strip()


async def _rerank_note_hits(*, query: str, hits: list[NoteHit], limit: int) -> list[NoteHit] | None:
    """Rerank fused hits with litellm; None means keep the fused order.

    Same call shape and graceful-fallback semantics as RAGService._rerank_candidates:
    provider errors and malformed responses log a warning and fall back.
    """
    rerank_model = _resolve_rerank_model()
    if not rerank_model or not hits:
        return None

    try:
        response = await litellm.arerank(
            model=rerank_model,
            query=query,
            documents=[hit.note for hit in hits],
            top_n=limit,
        )
    except EMBEDDING_FAILURE_ERROR_TYPES:
        logger.warning("memory.notes_search.rerank_failed", extra={"rerank_model": rerank_model}, exc_info=True)
        return None

    scored: list[tuple[NoteHit, float]] = []
    for result in _rerank_response_results(response):
        index = _rerank_result_value(result, "index")
        relevance_score = _rerank_result_value(result, "relevance_score")
        if not isinstance(index, int) or not isinstance(relevance_score, int | float):
            continue
        if not 0 <= index < len(hits):
            continue
        scored.append((hits[index], float(relevance_score)))

    if not scored:
        # Malformed response: keep the fused order, like the RAG rerank fallback.
        logger.warning("memory.notes_search.rerank_malformed", extra={"rerank_model": rerank_model})
        return None

    reranked: list[NoteHit] = []
    for hit, relevance_score in scored:
        if relevance_score < _RERANK_SCORE_FLOOR:
            continue
        hit.score = relevance_score
        reranked.append(hit)
    # An empty list here is a confident abstain: the reranker scored every
    # candidate below the floor.
    return reranked[:limit]


def _rerank_response_results(response: object) -> list[object]:
    raw_results = (
        cast("dict[str, object]", response).get("results")
        if isinstance(response, dict)
        else getattr(response, "results", None)
    )
    return cast("list[object]", raw_results) if isinstance(raw_results, list) else []


def _rerank_result_value(result: object, key: str) -> object:
    return cast("dict[str, object]", result).get(key) if isinstance(result, dict) else getattr(result, key, None)


def _format_vector(values: list[float]) -> str:
    return "[" + ",".join(str(value) for value in values) + "]"
