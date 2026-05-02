"""Document parsing using Unstructured."""

from __future__ import annotations

import re
from collections.abc import Sequence

from fastapi.concurrency import run_in_threadpool


_DEFAULT_LANGUAGES = ["eng"]
_WHITESPACE_RE = re.compile(r"\s+")
_CHAPTER_TITLE_RE = re.compile(r"^chapter\s+\d+\b", re.IGNORECASE)
_NUMBERED_CHAPTER_RE = re.compile(r"^\d+\s+\S+")
_CALLOUT_TITLES = {"note", "tip", "warning"}
_PRIMARY_SECTION_TITLES = {"preface", "epilogue", "introduction"}
_SKIPPED_SECTION_TITLES = {
    "acknowledgments",
    "contents",
    "how to contact us",
    "navigating this book",
    "o'reilly online learning",
    "praise for ai engineering",
    "revision history for the first edition",
    "table of contents",
    "using code examples",
}
_TRAILING_SECTION_TITLES = {
    "about the author",
    "about the authors",
    "colophon",
    "index",
}
_JUNK_TEXT_PREFIXES = (
    "copyright ",
    "printed in ",
    "published by ",
    "see http://oreilly.com/catalog/errata",
    "the o'reilly logo is a registered trademark",
    "the views expressed in this work",
)


def _normalize_text(text: str) -> str:
    """Normalize parser element text without changing its meaning."""
    return _WHITESPACE_RE.sub(" ", text).strip()


def _normalize_title(text: str) -> str:
    """Normalize section titles for filtering decisions."""
    return _normalize_text(text).casefold().replace("\u2019", "'")


def _looks_like_junk_text(text: str) -> bool:
    """Filter publisher metadata that harms retrieval more than it helps."""
    normalized = _normalize_title(text)
    if normalized == "[lsi]":
        return True
    if normalized.startswith(_JUNK_TEXT_PREFIXES):
        return True
    return bool(re.fullmatch(r"(?:97[89][- ]?)?[0-9][- 0-9]{8,}[0-9x]", normalized))


def _extract_plain_text_from_rows(rows: Sequence[tuple[str, str]]) -> str:
    """Return cleaned text when structural markers are absent or unreliable."""
    blocks: list[str] = []
    skip_section = False

    for category, text in rows:
        if not text:
            continue

        normalized_title = _normalize_title(text)
        if _looks_like_heading(category, text):
            if normalized_title in _TRAILING_SECTION_TITLES and blocks:
                break
            if normalized_title in _SKIPPED_SECTION_TITLES:
                skip_section = True
                continue
            skip_section = False

        if skip_section or _looks_like_junk_text(text):
            continue

        if category == "ListItem":
            blocks.append(f"- {text}")
        else:
            blocks.append(text)

    return "\n\n".join(blocks)


def _heading_level(title: str) -> int:
    """Pick a simple Markdown heading level from book section text."""
    normalized = _normalize_title(title)
    if _CHAPTER_TITLE_RE.match(title) or _NUMBERED_CHAPTER_RE.match(title) or normalized in _PRIMARY_SECTION_TITLES:
        return 1
    return 2


def _looks_like_heading(category: str, text: str) -> bool:
    """Detect headings from EPUBs that Unstructured labels as plain text."""
    if category == "Title":
        return True
    if category != "UncategorizedText" or len(text) > 96:
        return False

    normalized = _normalize_title(text)
    if normalized in _PRIMARY_SECTION_TITLES | _SKIPPED_SECTION_TITLES | _TRAILING_SECTION_TITLES | _CALLOUT_TITLES:
        return True
    if _NUMBERED_CHAPTER_RE.match(text):
        return True
    if text.endswith((".", ",", ";")):
        return False
    return text.isupper() or text.istitle()


def _is_body_start_heading(rows: Sequence[tuple[str, str]], index: int, text: str) -> bool:
    """Distinguish a real opening heading from a table-of-contents entry."""
    normalized = _normalize_title(text)
    is_opening_heading = (
        bool(_CHAPTER_TITLE_RE.match(text))
        or bool(_NUMBERED_CHAPTER_RE.match(text))
        or normalized in _PRIMARY_SECTION_TITLES
    )
    if not is_opening_heading:
        return False

    for next_category, next_text in rows[index + 1 :]:
        if next_text:
            return next_category == "NarrativeText"
    return False


def _extract_structured_text_from_elements(elements: Sequence[object]) -> str:
    """Convert Unstructured elements into Markdown-like book text."""
    rows = [
        (str(getattr(element, "category", type(element).__name__)), _normalize_text(str(element)))
        for element in elements
    ]
    blocks: list[str] = []
    skip_section = False
    seen_body_start = False

    for index, (category, text) in enumerate(rows):
        if not text:
            continue

        if _looks_like_heading(category, text):
            normalized_title = _normalize_title(text)
            if seen_body_start and normalized_title in _TRAILING_SECTION_TITLES:
                break
            is_body_start = _is_body_start_heading(rows, index, text)
            if not seen_body_start and not is_body_start:
                skip_section = True
                continue
            if normalized_title in _SKIPPED_SECTION_TITLES:
                skip_section = True
                continue
            if normalized_title in _CALLOUT_TITLES:
                skip_section = False
                blocks.append(f"**{text}.**")
                continue

            seen_body_start = True
            skip_section = False
            heading_prefix = "#" * _heading_level(text)
            blocks.append(f"{heading_prefix} {text}")
            continue

        if skip_section or _looks_like_junk_text(text):
            continue

        if category == "ListItem":
            blocks.append(f"- {text}")
        else:
            blocks.append(text)

    structured_text = "\n\n".join(blocks)
    if structured_text:
        return structured_text
    return _extract_plain_text_from_rows(rows)


def _extract_text_with_unstructured(file_path: str) -> str:
    """Extract structured text through Unstructured partitioning."""
    from unstructured.partition.auto import partition

    elements = partition(
        filename=file_path,
        strategy="auto",
        languages=_DEFAULT_LANGUAGES,
    )
    return _extract_structured_text_from_elements(elements)


class DocumentProcessor:
    """Document processing using Unstructured partitioning."""

    async def process_document(self, file_path: str, document_type: str) -> str:
        """Extract text from a document on disk."""
        del document_type
        return await run_in_threadpool(_extract_text_with_unstructured, file_path)
