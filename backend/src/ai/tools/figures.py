"""Openverse figure retrieval for lesson-writing, gated by vision verification."""

import base64
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, cast
from urllib.parse import unquote, urlsplit

import httpx
from pydantic import JsonValue

from src.ai.models import FigureVerification
from src.ai.tools.plan import FunctionToolDefinition, LocalToolTarget


_OPENVERSE_SEARCH_URL = "https://api.openverse.org/v1/images/"
_COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"
# Attribution-only licenses; excludes NC/ND so embedding stays commercially safe.
_ALLOWED_LICENSES = "by,by-sa,cc0,pdm"
_SEARCH_PAGE_SIZE = 20
_DISPLAY_THUMB_WIDTH = 1280
_DEFAULT_TIMEOUT_SECONDS = 15.0
# Wikimedia API etiquette requires an identifying User-Agent.
_USER_AGENT = "TalimioLessonFigures/1.0 (https://talimio.com)"
# Diagram-friendly formats rank first; photo formats (the usual junk) rank last.
_EXTENSION_SORT_RANK = {"svg": 0, "png": 1}
# Vision verifications run per candidate, so keep the cap small.
_DEFAULT_MAX_CANDIDATES = 3
# Below this confidence a match is downgraded to "none" rather than risk a misleading figure.
_CONFIDENCE_FLOOR = 0.55


@dataclass(frozen=True, slots=True)
class FigureCandidate:
    """One prefiltered Openverse hit with a single browser- and vision-usable image URL."""

    url: str
    title: str
    license: str
    attribution: str
    mime: str | None
    source: str
    foreign_landing_url: str


async def search_figure_candidates(
    concept: str,
    *,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> list[FigureCandidate]:
    """Search Openverse by concept and return deduped, license-filtered figure candidates.

    Search uses the concept alone: Openverse is AND-matched keyword search, so extra
    disambiguating words collapse recall to nothing. Disambiguation happens at the
    vision-verify gate instead, where `lesson_context` tells the model what to expect.

    Wikimedia hits are resolved through the Commons API because Openverse's own
    thumbnail proxy returns HTTP 424 for them. The resolve returns a sized raster
    thumb (PNG even for SVG files), so the one URL we keep is safe both for vision
    input and for direct embedding — what gets verified is what students see.
    """
    query = concept.strip()
    if not query:
        msg = "Field `concept` is required"
        raise ValueError(msg)

    headers = {"Accept": "application/json", "User-Agent": _USER_AGENT}
    async with httpx.AsyncClient(timeout=timeout_seconds, headers=headers) as client:
        results = await _search_openverse(client, query)
        candidates = _parse_openverse_results(results)
        wikimedia_candidates = [candidate for candidate in candidates if candidate.source == "wikimedia"]
        resolved = await _resolve_wikimedia_files(client, wikimedia_candidates)

    # Substitute resolved Wikimedia candidates in place to keep Openverse relevance order;
    # files Commons no longer knows are dropped.
    ordered: list[FigureCandidate] = []
    for candidate in candidates:
        if candidate.source != "wikimedia":
            ordered.append(candidate)
        elif candidate.url in resolved:
            ordered.append(resolved[candidate.url])

    deduped = _dedupe_by_url(ordered)
    deduped.sort(key=lambda candidate: _EXTENSION_SORT_RANK.get(_url_extension(candidate.url), 2))
    return deduped


async def _search_openverse(client: httpx.AsyncClient, query: str) -> list[JsonValue]:
    params: dict[str, str | int] = {
        "q": query,
        "license": _ALLOWED_LICENSES,
        "page_size": _SEARCH_PAGE_SIZE,
    }
    body = await _request_json(client, "GET", _OPENVERSE_SEARCH_URL, params=params, service="Openverse")
    results = body.get("results")
    return results if isinstance(results, list) else []


def _parse_openverse_results(results: list[JsonValue]) -> list[FigureCandidate]:
    candidates: list[FigureCandidate] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        candidate = _build_candidate(cast("Mapping[str, JsonValue]", item))
        if candidate is None:
            continue
        if candidate.source != "wikimedia" and _url_extension(candidate.url) == "svg":
            # Non-Wikimedia SVGs are skipped: no rasterized thumb exists for vision input.
            continue
        candidates.append(candidate)
    return candidates


def _build_candidate(item: Mapping[str, JsonValue]) -> FigureCandidate | None:
    url = str(item.get("url") or "").strip()
    license_code = str(item.get("license") or "").strip()
    if not url or not license_code:
        return None
    filetype = str(item.get("filetype") or "").strip() or _url_extension(url)
    return FigureCandidate(
        url=url,
        title=str(item.get("title") or "").strip(),
        license=_format_license(license_code, str(item.get("license_version") or "").strip()),
        attribution=str(item.get("attribution") or "").strip(),
        mime=f"image/{filetype}" if filetype else None,
        source=str(item.get("source") or "").strip(),
        foreign_landing_url=str(item.get("foreign_landing_url") or "").strip(),
    )


async def _resolve_wikimedia_files(
    client: httpx.AsyncClient, candidates: list[FigureCandidate]
) -> dict[str, FigureCandidate]:
    """Resolve Wikimedia candidates to live, display-sized `upload.wikimedia.org` URLs.

    Returns resolved candidates keyed by their original URL. One batched
    `imageinfo` query covers all candidates and doubles as a liveness check.
    """
    files_by_title = {f"File:{unquote(_url_filename(candidate.url))}": candidate for candidate in candidates}
    if not files_by_title:
        return {}

    params: dict[str, str | int] = {
        "action": "query",
        "format": "json",
        "prop": "imageinfo",
        "iiprop": "url|mime|size",
        "iiurlwidth": _DISPLAY_THUMB_WIDTH,
        "titles": "|".join(files_by_title),
    }
    body = await _request_json(client, "GET", _COMMONS_API_URL, params=params, service="Wikimedia Commons")
    query_block = body.get("query")
    if not isinstance(query_block, dict):
        return {}
    query_payload = cast("Mapping[str, JsonValue]", query_block)

    # Commons normalizes titles (underscores → spaces); map normalized titles back to ours.
    normalized = query_payload.get("normalized")
    for entry in normalized if isinstance(normalized, list) else []:
        if isinstance(entry, dict) and entry.get("from") in files_by_title:
            files_by_title[str(entry["to"])] = files_by_title.pop(str(entry["from"]))

    pages = query_payload.get("pages")
    if not isinstance(pages, dict):
        return {}

    resolved: dict[str, FigureCandidate] = {}
    for page in pages.values():
        if not isinstance(page, dict):
            continue
        candidate = files_by_title.get(str(page.get("title")))
        image_info = _first_image_info(cast("Mapping[str, JsonValue]", page))
        if candidate is None or image_info is None:
            continue
        url = str(image_info.get("thumburl") or image_info.get("url") or "").strip()
        if not url:
            continue
        mime = str(image_info.get("mime") or "").strip()
        resolved[candidate.url] = FigureCandidate(
            url=url,
            title=candidate.title,
            license=candidate.license,
            attribution=candidate.attribution,
            # The display thumb for an SVG is a rasterized PNG, not the original mime.
            mime="image/png" if url.endswith(".png") else (mime or candidate.mime),
            source=candidate.source,
            foreign_landing_url=candidate.foreign_landing_url,
        )
    return resolved


def _first_image_info(page: Mapping[str, JsonValue]) -> Mapping[str, JsonValue] | None:
    image_info = page.get("imageinfo")
    if isinstance(image_info, list) and image_info and isinstance(image_info[0], dict):
        return cast("Mapping[str, JsonValue]", image_info[0])
    return None


async def _request_json(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    params: dict[str, str | int],
    service: str,
) -> dict[str, JsonValue]:
    try:
        response = await client.request(method, url, params=params)
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        message = f"{service} request failed with status {error.response.status_code}"
        raise RuntimeError(message) from error
    except httpx.HTTPError as error:
        message = f"{service} request failed"
        raise RuntimeError(message) from error

    body = response.json()
    if not isinstance(body, dict):
        message = f"{service} returned an invalid response shape"
        raise TypeError(message)
    return cast("dict[str, JsonValue]", body)


def _dedupe_by_url(candidates: list[FigureCandidate]) -> list[FigureCandidate]:
    seen: set[str] = set()
    unique: list[FigureCandidate] = []
    for candidate in candidates:
        if candidate.url not in seen:
            seen.add(candidate.url)
            unique.append(candidate)
    return unique


def _url_filename(url: str) -> str:
    return urlsplit(url).path.rsplit("/", 1)[-1]


def _url_extension(url: str) -> str:
    filename = _url_filename(url)
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _format_license(code: str, version: str) -> str:
    if code == "pdm":
        return "Public Domain Mark"
    label = code.upper() if code == "cc0" else f"CC {code.upper()}"
    return f"{label} {version}".strip()


class FigureVerifier(Protocol):
    """Vision verify callable supplied by LLMClient.verify_figure_for_concept."""

    async def __call__(
        self, *, concept: str, image_url: str, lesson_context: str | None = None
    ) -> FigureVerification:
        """Verify whether one image is a load-bearing figure for the concept."""
        ...


class OpenverseFigureFinderTool:
    """Find one vision-verified, load-bearing figure for a concept, or report `none`.

    The whole look→re-search loop is kept inside this handler: search candidates,
    verify up to a small cap, stop early on an exact match, and fall back to the best
    related figure. The lesson-writer model just sees one honest result.
    """

    def __init__(
        self,
        *,
        verify: FigureVerifier,
        max_candidates: int = _DEFAULT_MAX_CANDIDATES,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._verify = verify
        self._max_candidates = max_candidates
        self._timeout_seconds = timeout_seconds

    async def execute(self, arguments: Mapping[str, object]) -> dict[str, JsonValue]:
        """Return one verified figure dict, or `{"match": "none"}` when nothing real fits."""
        concept = str(arguments.get("concept") or "").strip()
        if not concept:
            msg = "Field `concept` is required"
            raise ValueError(msg)
        raw_context = arguments.get("lesson_context")
        lesson_context = str(raw_context).strip() if isinstance(raw_context, str) else None

        candidates = await search_figure_candidates(concept, timeout_seconds=self._timeout_seconds)

        best: tuple[FigureCandidate, FigureVerification] | None = None
        headers = {"User-Agent": _USER_AGENT}
        async with httpx.AsyncClient(timeout=self._timeout_seconds, headers=headers, follow_redirects=True) as client:
            for candidate in candidates[: self._max_candidates]:
                # Verify on the bytes we fetch (our User-Agent works); the LLM provider's own
                # fetch of Wikimedia thumbs gets rate-limited (429), so inline the image instead.
                image_data_url = await _fetch_image_data_url(client, candidate)
                if image_data_url is None:
                    continue
                verification = await self._verify(
                    concept=concept, image_url=image_data_url, lesson_context=lesson_context
                )
                if verification.match == "none" or verification.confidence < _CONFIDENCE_FLOOR:
                    continue
                if verification.match == "exact":
                    return _figure_payload(candidate, verification)
                if best is None or verification.confidence > best[1].confidence:
                    best = (candidate, verification)

        if best is not None:
            return _figure_payload(*best)
        return {"match": "none"}


def build_figure_finder_function_tool(
    *,
    verify: FigureVerifier,
    max_candidates: int = _DEFAULT_MAX_CANDIDATES,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> FunctionToolDefinition:
    """Return the lesson-writer `find_lesson_figure` function tool."""
    tool = OpenverseFigureFinderTool(
        verify=verify, max_candidates=max_candidates, timeout_seconds=timeout_seconds
    )
    return FunctionToolDefinition(
        schema={
            "type": "function",
            "function": {
                "name": "find_lesson_figure",
                "description": (
                    "Find a real, load-bearing educational figure (diagram, schematic, anatomical "
                    "drawing, micrograph) for a science concept that has no native modality — biology, "
                    "physics, chemistry, anatomy. Do NOT use it for math or CS (use math/code components) "
                    "or for decoration. Each candidate is vision-verified before it is returned. "
                    'On success returns match "exact" or "related" with url, license, attribution, '
                    "caption and a caveat; on `related`, honor the caveat and you may adapt the surrounding "
                    'text to what the figure actually shows. Returns {"match": "none"} when no real figure '
                    "fits — generate your own explanation instead."
                ),
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "concept": {"type": "string"},
                        "lesson_context": {"type": "string"},
                    },
                    "required": ["concept"],
                },
            },
        },
        target=LocalToolTarget(execute=tool.execute),
    )


async def _fetch_image_data_url(client: httpx.AsyncClient, candidate: FigureCandidate) -> str | None:
    """Fetch the candidate image and return a base64 data URL, or None if it is not a live image."""
    try:
        response = await client.get(candidate.url)
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip()
    if not content_type:
        content_type = candidate.mime or "image/png"
    if not content_type.startswith("image/"):
        return None
    encoded = base64.b64encode(response.content).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


def _figure_payload(candidate: FigureCandidate, verification: FigureVerification) -> dict[str, JsonValue]:
    return {
        "match": verification.match,
        "confidence": verification.confidence,
        "url": candidate.url,
        "license": candidate.license,
        "attribution": candidate.attribution,
        "source_page": candidate.foreign_landing_url,
        "depicts": verification.depicts,
        "relevance": verification.relevance,
        "caveat": verification.caveat,
        "caption": verification.caption,
    }
