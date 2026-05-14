# ruff: noqa: S101

import asyncio
import uuid
from types import SimpleNamespace
from typing import Any, cast

import litellm
import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.rag.config import RAGConfig
from src.ai.rag.embeddings import VectorRAG
from src.ai.rag.exceptions import RagUnavailableError, RagValidationError
from src.ai.rag.schemas import SearchRequest, SearchResult
from src.ai.rag.service import RAGService


class _FailingSearchSession:
    async def execute(self, *_args: object, **_kwargs: object) -> None:
        raise SQLAlchemyError


class _UploadValidationSession:
    add_called = False

    def add(self, _value: object) -> None:
        self.add_called = True


class _UnusedSession:
    pass


class _SearchResultRows:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def mappings(self) -> _SearchResultRows:
        return self

    def all(self) -> list[dict[str, object]]:
        return self._rows

    def fetchall(self) -> list[SimpleNamespace]:
        return [SimpleNamespace(_mapping=row) for row in self._rows]


class _HybridSearchSession:
    def __init__(self, *, dense_rows: list[dict[str, object]], lexical_rows: list[dict[str, object]]) -> None:
        self.dense_rows = dense_rows
        self.lexical_rows = lexical_rows
        self.statements: list[str] = []
        self.params: list[dict[str, object] | None] = []

    async def execute(self, statement: object, params: dict[str, object] | None = None) -> _SearchResultRows:
        sql = str(statement)
        self.statements.append(sql)
        self.params.append(params)
        if "SET LOCAL" in sql:
            return _SearchResultRows([])
        if "websearch_to_tsquery" in sql:
            return _SearchResultRows(self.lexical_rows)
        return _SearchResultRows(self.dense_rows)


class _RecordingVectorRAG:
    def __init__(self, results: list[SearchResult]) -> None:
        self.results = results
        self.limits: list[int] = []

    async def search(
        self,
        session: AsyncSession,
        doc_type: str,
        query: str,
        limit: int,
        course_id: uuid.UUID | None = None,
    ) -> list[SearchResult]:
        _ = (session, doc_type, query, course_id)
        await asyncio.sleep(0)
        self.limits.append(limit)
        return self.results[:limit]


def _build_test_rag_config(*, rerank_model: str) -> RAGConfig:
    return RAGConfig(
        embedding_model="test-embedding",
        embedding_context_size=None,
        embedding_manual_retries=0,
        embedding_retry_delay_seconds=0,
        embedding_batch_size=1,
        embedding_output_dim=None,
        hnsw_ef_search=80,
        rerank_model=rerank_model,
        max_file_size_mb=10,
        chunk_size=400,
        chunk_overlap_ratio=0.12,
    )


def _build_search_result(chunk_id: str, score: float) -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id,
        content=f"Content for {chunk_id}",
        similarity_score=score,
        metadata={"source": chunk_id},
    )


@pytest.mark.asyncio
async def test_vector_search_database_failure_raises_rag_error() -> None:
    vector_rag = VectorRAG.__new__(VectorRAG)
    vector_rag.configured_embedding_dim = 3
    vector_rag._db_embedding_dim = None  # noqa: SLF001
    vector_rag._effective_embedding_dim = 3  # noqa: SLF001
    vector_rag._dimensions_validated = False  # noqa: SLF001

    with pytest.raises(RagUnavailableError):
        await vector_rag.search(
            _FailingSearchSession(),
            doc_type="course",
            query="hello",
            limit=3,
            course_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_upload_validation_rejects_empty_file_before_creating_document(monkeypatch: pytest.MonkeyPatch) -> None:
    service = RAGService()
    session = _UploadValidationSession()

    async def skip_course_check(*_args: Any, **_kwargs: Any) -> None:
        await asyncio.sleep(0)

    monkeypatch.setattr(service, "_ensure_course_owned", skip_course_check)

    with pytest.raises(RagValidationError):
        await service.upload_document(
            session=cast("AsyncSession", session),
            user_id=uuid.uuid4(),
            course_id=uuid.uuid4(),
            document_type="txt",
            title="Empty source",
            file_content=b"",
            filename="empty.txt",
        )

    assert session.add_called is False


def test_metadata_normalization_rejects_non_finite_floats() -> None:
    with pytest.raises(RagValidationError):
        VectorRAG._normalize_metadata({"score": float("nan")})  # noqa: SLF001


def test_search_request_rejects_whitespace_only_query() -> None:
    with pytest.raises(ValueError, match="Search query must not be empty"):
        SearchRequest(query="   ")


def test_embedding_response_validation_raises_typed_rag_error() -> None:
    with pytest.raises(RagUnavailableError):
        VectorRAG._normalize_embedding_response(cast("litellm.EmbeddingResponse", object()))  # noqa: SLF001


@pytest.mark.asyncio
async def test_store_embeddings_rejects_zero_valid_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    vector_rag = VectorRAG.__new__(VectorRAG)
    vector_rag.batch_size = 10

    async def skip_dimensions(*_args: object, **_kwargs: object) -> None:
        await asyncio.sleep(0)

    monkeypatch.setattr(vector_rag, "_ensure_dimensions", skip_dimensions)

    with pytest.raises(RagValidationError, match="No valid chunks to store"):
        await vector_rag.store_document_chunks_with_embeddings(
            cast("AsyncSession", _UnusedSession()),
            doc_type="course",
            doc_id=uuid.uuid4(),
            title="Empty source",
            chunks=["   "],
        )


@pytest.mark.asyncio
async def test_embedding_count_mismatch_raises_typed_rag_error(monkeypatch: pytest.MonkeyPatch) -> None:
    vector_rag = VectorRAG.__new__(VectorRAG)
    vector_rag.manual_retry_attempts = 0
    vector_rag.retry_backoff_seconds = 0

    def build_kwargs(texts: object) -> dict[str, object]:
        return {"input": texts}

    async def invoke_embedding(_kwargs: dict[str, object]) -> litellm.EmbeddingResponse:
        await asyncio.sleep(0)
        return cast("litellm.EmbeddingResponse", SimpleNamespace(data=[SimpleNamespace(embedding=[1.0, 2.0, 3.0])]))

    monkeypatch.setattr(vector_rag, "_build_embedding_kwargs", build_kwargs)
    monkeypatch.setattr(vector_rag, "_invoke_embedding", invoke_embedding)

    with pytest.raises(RagUnavailableError, match="unexpected number of embeddings"):
        await vector_rag.generate_embeddings(["one", "two"])


@pytest.mark.asyncio
async def test_hybrid_search_returns_exact_match_from_lexical_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    vector_rag = VectorRAG.__new__(VectorRAG)
    course_id = uuid.uuid4()
    dense_doc_id = uuid.uuid4()
    lexical_doc_id = uuid.uuid4()
    session = _HybridSearchSession(
        dense_rows=[
            {
                "doc_id": dense_doc_id,
                "doc_type": "course",
                "chunk_index": 0,
                "content": "General semantic neighbor without the rare heading.",
                "metadata": {"course_id": str(course_id)},
                "dense_score": 0.91,
            }
        ],
        lexical_rows=[
            {
                "doc_id": lexical_doc_id,
                "doc_type": "course",
                "chunk_index": 3,
                "content": "Section: ZXQ-17\n\nThe ZXQ-17 calibration heading explains the exact procedure.",
                "metadata": {"course_id": str(course_id), "section_path": "ZXQ-17"},
                "lexical_score": 0.42,
            }
        ],
    )

    async def skip_dimensions(*_args: object, **_kwargs: object) -> None:
        await asyncio.sleep(0)

    async def generate_embedding(_query: str) -> list[float]:
        await asyncio.sleep(0)
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr(vector_rag, "_ensure_dimensions", skip_dimensions)
    monkeypatch.setattr(vector_rag, "generate_embedding", generate_embedding)

    results = await vector_rag.search(
        cast("AsyncSession", session),
        doc_type="course",
        query="ZXQ-17",
        limit=1,
        course_id=course_id,
    )

    assert results[0].chunk_id == f"{lexical_doc_id}_3"
    assert "ZXQ-17 calibration heading" in results[0].content
    assert results[0].metadata["lexical_rank"] == 1
    assert results[0].metadata["lexical_score"] == pytest.approx(0.42)
    assert results[0].metadata["fused_score"] == pytest.approx(1 / 61)
    assert any("metadata->>'course_id' = :course_id" in statement for statement in session.statements)
    assert any("websearch_to_tsquery('english', :query)" in statement for statement in session.statements)
    assert session.params[1] is not None
    assert session.params[1]["candidate_limit"] == 4
    assert session.params[1]["course_id"] == str(course_id)


@pytest.mark.asyncio
async def test_search_course_documents_skips_rerank_when_model_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    service = RAGService()
    service.config = _build_test_rag_config(rerank_model="")
    vector_rag = _RecordingVectorRAG([_build_search_result("first", 0.9), _build_search_result("second", 0.8)])
    service._vector_rag = cast("VectorRAG", vector_rag)  # noqa: SLF001

    async def fail_if_called(*_args: object, **_kwargs: object) -> object:
        await asyncio.sleep(0)
        pytest.fail("arerank should not be called when RAG_RERANK_MODEL is empty")

    monkeypatch.setattr(litellm, "arerank", fail_if_called)

    results = await service.search_course_documents(
        cast("AsyncSession", _UnusedSession()), uuid.uuid4(), "query", top_k=2
    )

    assert [result.chunk_id for result in results] == ["first", "second"]
    assert vector_rag.limits == [2]


@pytest.mark.asyncio
async def test_search_course_documents_reranks_with_litellm_scores(monkeypatch: pytest.MonkeyPatch) -> None:
    service = RAGService()
    service.config = _build_test_rag_config(rerank_model="test-reranker")
    vector_rag = _RecordingVectorRAG(
        [
            _build_search_result("first", 0.9),
            _build_search_result("second", 0.8),
            _build_search_result("third", 0.7),
            _build_search_result("fourth", 0.6),
        ]
    )
    service._vector_rag = cast("VectorRAG", vector_rag)  # noqa: SLF001

    async def rerank(*, model: str, query: str, documents: list[str], top_n: int) -> SimpleNamespace:
        await asyncio.sleep(0)
        assert model == "test-reranker"
        assert query == "query"
        assert documents == [result.content for result in vector_rag.results]
        assert top_n == 2
        return SimpleNamespace(
            results=[
                {"index": 2, "relevance_score": 0.99},
                {"index": 0, "relevance_score": 0.88},
            ]
        )

    monkeypatch.setattr(litellm, "arerank", rerank)

    results = await service.search_course_documents(
        cast("AsyncSession", _UnusedSession()), uuid.uuid4(), "query", top_k=2
    )

    assert vector_rag.limits == [8]
    assert [result.chunk_id for result in results] == ["third", "first"]
    assert [result.similarity_score for result in results] == [0.99, 0.88]
    assert results[0].metadata["retrieval_score"] == pytest.approx(0.7)
    assert results[0].metadata["rerank_score"] == pytest.approx(0.99)


@pytest.mark.asyncio
async def test_search_course_documents_falls_back_when_reranker_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    service = RAGService()
    service.config = _build_test_rag_config(rerank_model="test-reranker")
    vector_rag = _RecordingVectorRAG([_build_search_result("first", 0.9), _build_search_result("second", 0.8)])
    service._vector_rag = cast("VectorRAG", vector_rag)  # noqa: SLF001

    async def fail_rerank(*_args: object, **_kwargs: object) -> object:
        await asyncio.sleep(0)
        raise litellm.Timeout(message="timeout", model="test-reranker", llm_provider="test")

    monkeypatch.setattr(litellm, "arerank", fail_rerank)

    results = await service.search_course_documents(
        cast("AsyncSession", _UnusedSession()), uuid.uuid4(), "query", top_k=2
    )

    assert vector_rag.limits == [8]
    assert [result.chunk_id for result in results] == ["first", "second"]
    assert [result.similarity_score for result in results] == [0.9, 0.8]


@pytest.mark.asyncio
async def test_search_course_documents_falls_back_when_reranker_response_is_malformed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = RAGService()
    service.config = _build_test_rag_config(rerank_model="test-reranker")
    vector_rag = _RecordingVectorRAG([_build_search_result("first", 0.9), _build_search_result("second", 0.8)])
    service._vector_rag = cast("VectorRAG", vector_rag)  # noqa: SLF001

    async def malformed_rerank(*_args: object, **_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(0)
        return SimpleNamespace(results=[{"unexpected": "shape"}])

    monkeypatch.setattr(litellm, "arerank", malformed_rerank)

    results = await service.search_course_documents(
        cast("AsyncSession", _UnusedSession()), uuid.uuid4(), "query", top_k=2
    )

    assert vector_rag.limits == [8]
    assert [result.chunk_id for result in results] == ["first", "second"]
    assert [result.similarity_score for result in results] == [0.9, 0.8]


@pytest.mark.asyncio
async def test_search_course_documents_skips_rerank_when_model_is_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    service = RAGService()
    service.config = _build_test_rag_config(rerank_model="   ")
    vector_rag = _RecordingVectorRAG([_build_search_result("first", 0.9), _build_search_result("second", 0.8)])
    service._vector_rag = cast("VectorRAG", vector_rag)  # noqa: SLF001

    async def fail_if_called(*_args: object, **_kwargs: object) -> object:
        await asyncio.sleep(0)
        pytest.fail("arerank should not be called when RAG_RERANK_MODEL is blank")

    monkeypatch.setattr(litellm, "arerank", fail_if_called)

    results = await service.search_course_documents(
        cast("AsyncSession", _UnusedSession()), uuid.uuid4(), "query", top_k=2
    )

    assert [result.chunk_id for result in results] == ["first", "second"]
    assert vector_rag.limits == [2]
