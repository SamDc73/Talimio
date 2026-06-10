"""Integration test for lesson figure retrieval end-to-end flow.

Tests the complete pipeline: Openverse search → candidate filtering → vision verification → MDX output.
External services are mocked so this runs in CI without API keys.
"""
# ruff: noqa: S101, PLC2701, ARG001, RUF029, RUF069, D202

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import httpx
import pytest
from _pytest.monkeypatch import MonkeyPatch

from src.ai.models import FigureVerification
from src.ai.tools.figures import (
    FigureCandidate,
    OpenverseFigureFinderTool,
    _build_figure_mdx,
)


# Sample Openverse API response for mocking
_FAKE_OPENVERS_RESULTS: list[Mapping[str, Any]] = [
    {
        "url": "https://live.staticflickr.com/original.jpg",
        "thumbnail": "https://api.openverse.org/image/thumb.jpg",
        "license": "by",
        "license_version": "4.0",
        "source": "flickr",
        "title": "Neuron structure",
        "attribution": 'Photo by "Jane Doe"',
        "foreign_landing_url": "https://example.test/source",
        "filetype": "jpg",
    },
    {
        "url": "https://upload.wikimedia.org/wikipedia/commons/1/1a/test.svg",
        "thumbnail": None,
        "license": "cc0",
        "license_version": "1.0",
        "source": "wikimedia",
        "title": "Test diagram",
        "attribution": "Wikimedia Commons",
        "foreign_landing_url": "https://commons.wikimedia.org/wiki/File:test.svg",
        "filetype": "svg",
    },
]


@pytest.mark.asyncio
async def test_figure_tool_end_to_end(monkeypatch: MonkeyPatch) -> None:
    """Full integration: search → verify → MDX output with proper escaping."""

    async def fake_search(concept: str, *, timeout_seconds: float) -> list[FigureCandidate]:
        await asyncio.sleep(0)
        # Return parsed candidates from mock data
        from src.ai.tools.figures import _parse_openverse_results

        return _parse_openverse_results(_FAKE_OPENVERS_RESULTS)

    async def fake_verify(*, concept: str, image_url: str, lesson_context: str | None = None) -> FigureVerification:
        await asyncio.sleep(0)
        # Accept the flickr thumbnail (Openverse proxy), reject wikimedia
        if "openverse.org" in image_url:
            return FigureVerification(
                match="exact",
                confidence=0.94,
                depicts='A "synapse" diagram',
                relevance="Shows the synaptic gap and vesicles",
                caption='A "synapse" diagram with vesicles',
            )
        return FigureVerification(match="none", confidence=0.0)

    monkeypatch.setattr("src.ai.tools.figures.search_figure_candidates", fake_search)

    tool = OpenverseFigureFinderTool(verify=fake_verify)
    result = await tool.execute({"concept": "synapse", "lesson_context": "biology, synaptic transmission"})

    # Verify structure
    assert result["match"] == "exact"
    assert result["confidence"] == 0.94
    assert result["url"] == "https://api.openverse.org/image/thumb.jpg"
    assert result["license"] == "CC BY 4.0"
    assert result["attribution"] == 'Photo by "Jane Doe"'
    assert result["caption"] == 'A "synapse" diagram with vesicles'
    assert result["source_page"] == "https://example.test/source"

    # Verify MDX is properly escaped for JSX expression props
    expected_mdx = (
        '<Figure src={"https://api.openverse.org/image/thumb.jpg"} alt={"A \\"synapse\\" diagram"} '
        'caption={"A \\"synapse\\" diagram with vesicles"} attribution={"Photo by \\"Jane Doe\\""} '
        'license={"CC BY 4.0"} sourcePage={"https://example.test/source"} />'
    )
    assert result["figure_mdx"] == expected_mdx


@pytest.mark.asyncio
async def test_figure_tool_returns_none_when_no_match(monkeypatch: MonkeyPatch) -> None:
    """When vision rejects all candidates, return none."""

    async def fake_search(concept: str, *, timeout_seconds: float) -> list[FigureCandidate]:
        await asyncio.sleep(0)
        from src.ai.tools.figures import _parse_openverse_results

        return _parse_openverse_results(_FAKE_OPENVERS_RESULTS)

    async def fake_verify(*, concept: str, image_url: str, lesson_context: str | None = None) -> FigureVerification:
        await asyncio.sleep(0)
        return FigureVerification(match="none", confidence=0.0)

    monkeypatch.setattr("src.ai.tools.figures.search_figure_candidates", fake_search)

    tool = OpenverseFigureFinderTool(verify=fake_verify)
    result = await tool.execute({"concept": "synapse"})

    assert result == {"match": "none"}


@pytest.mark.asyncio
async def test_figure_tool_returns_related_with_caveat(monkeypatch: MonkeyPatch) -> None:
    """When vision returns related match, include caveat in output."""

    async def fake_search(concept: str, *, timeout_seconds: float) -> list[FigureCandidate]:
        await asyncio.sleep(0)
        from src.ai.tools.figures import _parse_openverse_results

        return _parse_openverse_results(_FAKE_OPENVERS_RESULTS)

    async def fake_verify(*, concept: str, image_url: str, lesson_context: str | None = None) -> FigureVerification:
        await asyncio.sleep(0)
        return FigureVerification(
            match="related",
            confidence=0.75,
            depicts="A neuron",
            relevance="Shows a neuron but not the synapse",
            caveat="This shows a neuron cell body, not the synaptic junction",
            caption="A neuron diagram",
        )

    monkeypatch.setattr("src.ai.tools.figures.search_figure_candidates", fake_search)

    tool = OpenverseFigureFinderTool(verify=fake_verify)
    result = await tool.execute({"concept": "synapse"})

    assert result["match"] == "related"
    assert result["caveat"] == "This shows a neuron cell body, not the synaptic junction"
    assert result["figure_mdx"]  # Should have generated MDX


@pytest.mark.asyncio
async def test_search_candidates_prefers_thumbnails_for_non_wikimedia() -> None:
    """Non-Wikimedia sources should use thumbnail URLs when available."""
    from src.ai.tools.figures import _parse_openverse_results

    candidates = _parse_openverse_results(_FAKE_OPENVERS_RESULTS)

    flickr = next(c for c in candidates if c.source == "flickr")
    assert flickr.url == "https://api.openverse.org/image/thumb.jpg"

    wikimedia = next(c for c in candidates if c.source == "wikimedia")
    assert wikimedia.url == "https://upload.wikimedia.org/wikipedia/commons/1/1a/test.svg"


@pytest.mark.asyncio
async def test_search_skips_non_wikimedia_svg() -> None:
    """SVG files from non-Wikimedia sources are skipped (no raster thumb available)."""
    from src.ai.tools.figures import _parse_openverse_results

    svg_only = [
        {
            "url": "https://example.com/diagram.svg",
            "thumbnail": None,
            "license": "cc0",
            "license_version": "1.0",
            "source": "unknown",
            "title": "SVG diagram",
            "attribution": "Unknown",
            "foreign_landing_url": "https://example.com",
            "filetype": "svg",
        }
    ]

    candidates = _parse_openverse_results(svg_only)
    assert len(candidates) == 0


@pytest.mark.asyncio
async def test_wikimedia_files_resolved_through_commons(monkeypatch: MonkeyPatch) -> None:
    """Wikimedia SVG files are resolved to raster thumbnails via Commons API."""

    # Mock Commons API response
    fake_commons_response = {
        "query": {
            "pages": {
                "123": {
                    "title": "File:test.svg",
                    "imageinfo": [
                        {
                            "thumburl": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1a/test.svg/500px-test.svg.png",
                            "url": "https://upload.wikimedia.org/wikipedia/commons/1/1a/test.svg",
                            "mime": "image/svg+xml",
                        }
                    ],
                }
            }
        }
    }

    async def fake_request_json(
        client: httpx.AsyncClient,
        method: str,
        url: str,
        *,
        params: dict[str, str | int],
        service: str,
    ) -> dict[str, Any]:
        await asyncio.sleep(0)
        return fake_commons_response

    monkeypatch.setattr("src.ai.tools.figures._request_json", fake_request_json)

    candidate = FigureCandidate(
        url="https://upload.wikimedia.org/wikipedia/commons/1/1a/test.svg",
        title="Test diagram",
        license="CC0",
        attribution="Wikimedia Commons",
        mime="image/svg+xml",
        source="wikimedia",
        foreign_landing_url="https://commons.wikimedia.org/wiki/File:test.svg",
    )

    from src.ai.tools.figures import _resolve_wikimedia_files

    async with httpx.AsyncClient() as client:
        resolved = await _resolve_wikimedia_files(client, [candidate])

    assert candidate.url in resolved
    resolved_candidate = resolved[candidate.url]
    assert resolved_candidate.url.endswith(".png")
    assert resolved_candidate.mime == "image/png"


@pytest.mark.asyncio
async def test_build_figure_mdx_escapes_quotes() -> None:
    """MDX output properly escapes quotes using JSON-style JSX expression props."""

    candidate = FigureCandidate(
        url="https://example.com/image.png",
        title="Test",
        license="CC BY 4.0",
        attribution='Photo by "Jane Doe"',
        mime="image/png",
        source="test",
        foreign_landing_url="https://example.com/source",
    )

    verification = FigureVerification(
        match="exact",
        confidence=0.9,
        depicts='A "test" image',
        relevance="Shows testing",
        caption='A "test" image with quotes',
    )

    mdx = _build_figure_mdx(candidate, verification)

    # Verify quotes are escaped with backslashes inside JSON strings
    assert 'attribution={"Photo by \\"Jane Doe\\""}' in mdx
    assert 'caption={"A \\"test\\" image with quotes"}' in mdx
    assert 'alt={"A \\"test\\" image"}' in mdx

    # Verify the MDX is valid by checking it compiles without errors
    # (In a real test, you'd compile with @mdx-js/mdx)
    assert mdx.startswith("<Figure ")
    assert mdx.endswith(" />")
