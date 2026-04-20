"""Wikipedia page resolution tool for lesson-writing side context."""

import asyncio
from collections.abc import Sequence
from typing import Any
from urllib.parse import quote

import httpx

from src.ai.tools.plan import FunctionToolDefinition, LocalToolTarget


_WIKIPEDIA_SEARCH_URL = "https://en.wikipedia.org/w/api.php"
_WIKIPEDIA_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
_DEFAULT_TIMEOUT_SECONDS = 10.0
_MAX_BATCH_TERMS = 10
_SEARCH_RESULT_LIMIT = 5


class WikipediaPageResolverTool:
    """Resolve learner-friendly terms to canonical Wikipedia page keys."""

    def __init__(self, *, timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS) -> None:
        self._timeout_seconds = timeout_seconds

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Resolve one or more terms against Wikipedia."""
        terms = _parse_terms(arguments)
        pages = await self._resolve_terms(terms)
        return {"pages": pages}

    async def _resolve_terms(self, terms: Sequence[str]) -> list[dict[str, Any]]:
        return await asyncio.gather(*(self._resolve_term(term) for term in terms))

    async def _resolve_term(self, term: str) -> dict[str, Any]:
        summary = await self._fetch_summary(term)
        if summary is not None:
            return _build_result(term, summary)

        disambiguation_result: dict[str, Any] | None = None
        for candidate_title in await self._search_candidate_titles(term):
            candidate_summary = await self._fetch_summary(candidate_title)
            if candidate_summary is None:
                continue
            candidate_result = _build_result(term, candidate_summary)
            if candidate_result["found"]:
                return candidate_result
            if candidate_result["is_disambiguation"] and disambiguation_result is None:
                disambiguation_result = candidate_result

        return disambiguation_result or _missing_result(term)

    async def _fetch_summary(self, title: str) -> dict[str, Any] | None:
        normalized_title = quote(title.replace(" ", "_"), safe="")
        return await self._request_json(url=_WIKIPEDIA_SUMMARY_URL.format(title=normalized_title))

    async def _search_candidate_titles(self, term: str) -> list[str]:
        body = await self._request_json(
            url=_WIKIPEDIA_SEARCH_URL,
            params={
                "action": "query",
                "format": "json",
                "list": "search",
                "origin": "*",
                "srlimit": _SEARCH_RESULT_LIMIT,
                "srsearch": term,
            },
        )
        if body is None:
            return []
        query_block = body.get("query")
        if not isinstance(query_block, dict):
            return []
        search_results = query_block.get("search")
        if not isinstance(search_results, list):
            return []

        titles: list[str] = []
        for item in search_results:
            if not isinstance(item, dict):
                continue
            title = item.get("title")
            if isinstance(title, str) and title.strip():
                titles.append(title.strip())
        return titles

    async def _request_json(self, *, url: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        headers = {"Accept": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds, headers=headers) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                return None
            status_code = error.response.status_code
            message = f"Wikipedia request failed with status {status_code}"
            raise RuntimeError(message) from error
        except httpx.HTTPError as error:
            msg = "Wikipedia request failed"
            raise RuntimeError(msg) from error

        body = response.json()
        if not isinstance(body, dict):
            msg = "Wikipedia returned an invalid response shape"
            raise TypeError(msg)
        return body


def build_wikipedia_resolver_function_tool(*, timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS) -> FunctionToolDefinition:
    """Return the lesson-writer Wikipedia resolver function tool."""
    tool = WikipediaPageResolverTool(timeout_seconds=timeout_seconds)
    return FunctionToolDefinition(
        schema={
            "type": "function",
            "function": {
                "name": "resolve_wikipedia_pages",
                "description": (
                    "Resolve uncertain side-context terms to canonical English Wikipedia page keys. "
                    "Return only the original term, whether a page was found, the canonical key, the page title, "
                    "and whether the result is a disambiguation page."
                ),
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "terms": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "maxItems": _MAX_BATCH_TERMS,
                        }
                    },
                    "required": ["terms"],
                },
            },
        },
        target=LocalToolTarget(execute=tool.execute),
    )


def _parse_terms(arguments: dict[str, Any]) -> list[str]:
    raw_terms = arguments.get("terms")
    if not isinstance(raw_terms, list):
        msg = "Field `terms` must be an array of strings"
        raise TypeError(msg)
    if not raw_terms:
        msg = "Field `terms` must include at least one term"
        raise ValueError(msg)
    if len(raw_terms) > _MAX_BATCH_TERMS:
        msg = f"Field `terms` must include at most {_MAX_BATCH_TERMS} terms"
        raise ValueError(msg)

    terms: list[str] = []
    for raw_term in raw_terms:
        if not isinstance(raw_term, str):
            msg = "Field `terms` must only contain strings"
            raise TypeError(msg)
        normalized_term = raw_term.strip()
        if not normalized_term:
            msg = "Field `terms` must not contain empty strings"
            raise ValueError(msg)
        terms.append(normalized_term)
    return terms


def _build_result(original_term: str, summary: dict[str, Any]) -> dict[str, Any]:
    page_title = _extract_page_title(summary)
    page_type = str(summary.get("type", "")).strip().lower()
    if page_type == "disambiguation":
        return {
            "original_term": original_term,
            "found": False,
            "key": None,
            "title": page_title,
            "is_disambiguation": True,
        }

    if not page_title:
        return _missing_result(original_term)

    return {
        "original_term": original_term,
        "found": True,
        "key": page_title.replace(" ", "_"),
        "title": page_title,
        "is_disambiguation": False,
    }


def _extract_page_title(summary: dict[str, Any]) -> str | None:
    titles_block = summary.get("titles")
    if isinstance(titles_block, dict):
        canonical_title = titles_block.get("canonical")
        if isinstance(canonical_title, str) and canonical_title.strip():
            return canonical_title.strip()

    title = summary.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return None


def _missing_result(original_term: str) -> dict[str, Any]:
    return {
        "original_term": original_term,
        "found": False,
        "key": None,
        "title": None,
        "is_disambiguation": False,
    }
