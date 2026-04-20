# ruff: noqa: S101

import asyncio
from typing import Never

import pytest
from _pytest.monkeypatch import MonkeyPatch

from src.ai.tools.wikipedia import WikipediaPageResolverTool


@pytest.mark.asyncio
async def test_wikipedia_resolver_returns_canonical_page_for_direct_summary(monkeypatch: MonkeyPatch) -> None:
    tool = WikipediaPageResolverTool()

    async def fake_fetch_summary(title: str) -> dict[str, object]:
        await asyncio.sleep(0)
        assert title == "Leibniz's notation"
        return {
            "type": "standard",
            "title": "Leibniz's notation",
            "titles": {"canonical": "Leibniz's notation"},
        }

    async def fail_search(_term: str) -> Never:
        await asyncio.sleep(0)
        msg = "Search fallback should not run when direct summary resolves"
        raise AssertionError(msg)

    monkeypatch.setattr(tool, "_fetch_summary", fake_fetch_summary)
    monkeypatch.setattr(tool, "_search_candidate_titles", fail_search)

    result = await tool.execute({"terms": ["Leibniz's notation"]})

    assert result == {
        "pages": [
            {
                "original_term": "Leibniz's notation",
                "found": True,
                "key": "Leibniz's_notation",
                "title": "Leibniz's notation",
                "is_disambiguation": False,
            }
        ]
    }


@pytest.mark.asyncio
async def test_wikipedia_resolver_uses_search_fallback_for_uncertain_term(monkeypatch: MonkeyPatch) -> None:
    tool = WikipediaPageResolverTool()

    async def fake_fetch_summary(title: str) -> dict[str, object] | None:
        await asyncio.sleep(0)
        if title == "Euler method":
            return None
        assert title == "Euler's method"
        return {
            "type": "standard",
            "title": "Euler's method",
            "titles": {"canonical": "Euler's method"},
        }

    async def fake_search(term: str) -> list[str]:
        await asyncio.sleep(0)
        assert term == "Euler method"
        return ["Euler's method"]

    monkeypatch.setattr(tool, "_fetch_summary", fake_fetch_summary)
    monkeypatch.setattr(tool, "_search_candidate_titles", fake_search)

    result = await tool.execute({"terms": ["Euler method"]})

    assert result == {
        "pages": [
            {
                "original_term": "Euler method",
                "found": True,
                "key": "Euler's_method",
                "title": "Euler's method",
                "is_disambiguation": False,
            }
        ]
    }


@pytest.mark.asyncio
async def test_wikipedia_resolver_rejects_disambiguation_pages(monkeypatch: MonkeyPatch) -> None:
    tool = WikipediaPageResolverTool()

    async def fake_fetch_summary(title: str) -> dict[str, object]:
        await asyncio.sleep(0)
        assert title == "Taylor"
        return {
            "type": "disambiguation",
            "title": "Taylor",
            "titles": {"canonical": "Taylor"},
        }

    async def fail_search(_term: str) -> Never:
        await asyncio.sleep(0)
        msg = "Search fallback should not run for direct disambiguation pages"
        raise AssertionError(msg)

    monkeypatch.setattr(tool, "_fetch_summary", fake_fetch_summary)
    monkeypatch.setattr(tool, "_search_candidate_titles", fail_search)

    result = await tool.execute({"terms": ["Taylor"]})

    assert result == {
        "pages": [
            {
                "original_term": "Taylor",
                "found": False,
                "key": None,
                "title": "Taylor",
                "is_disambiguation": True,
            }
        ]
    }
