"""Local web search function tool (Exa-backed)."""

from typing import Any

import httpx

from src.ai.tools.plan import FunctionToolDefinition, LocalToolTarget


_EXA_SEARCH_URL = "https://api.exa.ai/search"


class ExaWebSearchTool:
    """Thin Exa client used by the local `web_search` function tool."""

    def __init__(
        self,
        *,
        api_key: str,
        timeout_seconds: float,
        default_max_results: int,
    ) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._default_max_results = default_max_results

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a local Exa search and return normalized result snippets."""
        query, limit, include_domains = _parse_web_search_arguments(arguments, self._default_max_results)
        payload = _build_exa_payload(query=query, limit=limit, include_domains=include_domains)
        body = await self._request_exa(payload)
        return {"query": query, "results": _extract_results(body)}

    async def _request_exa(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"x-api-key": self._api_key, "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(_EXA_SEARCH_URL, json=payload, headers=headers)
                response.raise_for_status()
        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code
            message = f"Local web_search failed with Exa status {status_code}"
            raise RuntimeError(message) from error
        except httpx.HTTPError as error:
            msg = "Local web_search request failed"
            raise RuntimeError(msg) from error

        body = response.json()
        if not isinstance(body, dict):
            msg = "Local web_search returned an invalid Exa response shape"
            raise TypeError(msg)
        return body


def build_web_search_function_tool(
    *,
    api_key: str | None,
    timeout_seconds: float,
    default_max_results: int,
) -> FunctionToolDefinition | None:
    """Return a local web_search tool definition when Exa is configured."""
    normalized_key = (api_key or "").strip()
    if not normalized_key:
        return None

    tool = ExaWebSearchTool(
        api_key=normalized_key,
        timeout_seconds=timeout_seconds,
        default_max_results=default_max_results,
    )

    return FunctionToolDefinition(
        schema={
            "type": "function",
            "function": {
                "name": "web_search",
                "description": (
                    "Search the public web via Exa and return concise result snippets with source URLs."
                ),
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "query": {"type": "string"},
                        "num_results": {"type": "integer", "minimum": 1, "maximum": 10},
                        "include_domains": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        target=LocalToolTarget(execute=tool.execute),
    )


def _normalize_domain_list(raw_value: Any) -> list[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, str):
        normalized = raw_value.strip()
        return [normalized] if normalized else []
    if not isinstance(raw_value, list):
        return []
    domains: list[str] = []
    for item in raw_value:
        if not isinstance(item, str):
            continue
        normalized = item.strip()
        if normalized:
            domains.append(normalized)
    return domains


def _parse_web_search_arguments(arguments: dict[str, Any], default_max_results: int) -> tuple[str, int, list[str]]:
    query = str(arguments.get("query", "")).strip()
    if not query:
        msg = "Field `query` is required"
        raise ValueError(msg)

    raw_limit = arguments.get("num_results")
    limit = int(raw_limit) if raw_limit is not None else default_max_results
    if limit < 1:
        msg = "Field `num_results` must be >= 1"
        raise ValueError(msg)
    limit = min(limit, 10)
    include_domains = _normalize_domain_list(arguments.get("include_domains"))
    return query, limit, include_domains


def _build_exa_payload(*, query: str, limit: int, include_domains: list[str]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "query": query,
        "numResults": limit,
        "type": "auto",
        "contents": {"text": True, "highlights": {"numSentences": 2}},
    }
    if include_domains:
        payload["includeDomains"] = include_domains
    return payload


def _extract_results(body: dict[str, Any]) -> list[dict[str, Any]]:
    raw_results = body.get("results")
    if not isinstance(raw_results, list):
        return []
    results: list[dict[str, Any]] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", "")).strip()
        if not url:
            continue
        title = str(item.get("title", "")).strip()
        text_value = str(item.get("text", "")).strip()
        snippet = _extract_snippet(item, text_value)
        results.append({"title": title, "url": url, "snippet": snippet})
    return results


def _extract_snippet(item: dict[str, Any], fallback_text: str) -> str:
    highlights = item.get("highlights")
    if isinstance(highlights, list):
        for highlight in highlights:
            if isinstance(highlight, str):
                snippet = highlight.strip()
                if snippet:
                    return snippet

    if fallback_text:
        if len(fallback_text) <= 420:
            return fallback_text
        return f"{fallback_text[:417]}..."
    return ""
