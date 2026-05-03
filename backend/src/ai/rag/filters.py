"""Small post-retrieval filters for RAG results."""

from __future__ import annotations

import re

from src.ai.rag.schemas import SearchResult


_WORD_RE = re.compile(r"[a-z0-9]+")


def _word_set(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.casefold()))


def _jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def deduplicate_by_similarity(results: list[SearchResult], *, threshold: float = 0.92) -> list[SearchResult]:
    """Drop near-duplicate chunks while preserving higher-ranked results."""
    kept: list[SearchResult] = []
    kept_word_sets: list[set[str]] = []

    for result in results:
        words = _word_set(result.content)
        if any(_jaccard_similarity(words, existing) >= threshold for existing in kept_word_sets):
            continue
        kept.append(result)
        kept_word_sets.append(words)

    return kept
