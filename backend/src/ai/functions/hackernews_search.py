"""HackerNews search functionality.

This module handles searching HackerNews for educational discussions,
tutorials, and community insights on technical topics.
"""

import logging
import time
from typing import Any

import httpx

from .registry import register_function


logger = logging.getLogger(__name__)


@register_function(
    {
        "type": "function",
        "name": "search_hackernews_discussions",
        "description": "Find educational discussions and resources from HackerNews community",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Learning topic to search for"},
                "content_type": {
                    "type": "string",
                    "enum": ["tutorial", "discussion", "resource", "tool", "any"],
                    "description": "Type of HN content",
                },
                "time_range": {
                    "type": "string",
                    "enum": ["day", "week", "month", "year", "all"],
                    "description": "Time range for search",
                },
                "min_points": {"type": "integer", "minimum": 1, "description": "Minimum upvotes", "default": 10},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "required": ["topic"],
            "additionalProperties": False,
        },
        "strict": True,
    }
)
async def search_hackernews_discussions(
    topic: str,
    content_type: str = "any",
    time_range: str = "month",
    min_points: int = 10,
    max_results: int = 10
) -> dict[str, Any]:
    """Search HackerNews for educational discussions and resources.

    Args:
        topic: Learning topic to search for
        content_type: Type of content to find (tutorial, discussion, resource, tool, any)
        time_range: Time range for search (day, week, month, year, all)
        min_points: Minimum number of upvotes
        max_results: Maximum number of results

    Returns
    -------
        Dictionary with HackerNews search results
    """
    try:
        logger.info("Searching HackerNews for topic: %s, type: %s", topic, content_type)

        # Use HackerNews Search API (Algolia)
        base_url = "https://hn.algolia.com/api/v1/search"

        # Build search query
        search_terms = [topic]
        if content_type != "any":
            if content_type == "tutorial":
                search_terms.extend(["tutorial", "guide", "how to"])
            elif content_type == "discussion":
                search_terms.extend(["discussion", "ask HN"])
            elif content_type == "resource":
                search_terms.extend(["resource", "collection", "awesome"])
            elif content_type == "tool":
                search_terms.extend(["tool", "library", "framework"])

        query = " ".join(search_terms)

        # Time range mapping
        time_filters = {
            "day": int(time.time()) - 86400,
            "week": int(time.time()) - 604800,
            "month": int(time.time()) - 2592000,
            "year": int(time.time()) - 31536000,
            "all": 0,
        }

        params = {
            "query": query,
            "tags": "story",
            "hitsPerPage": max_results * 2,  # Get more to filter by points
            "minWordSizefor1Typo": 4,
            "minWordSizefor2Typos": 8,
            "numericFilters": f"points>={min_points}",
        }

        if time_range != "all":
            params["numericFilters"] += f",created_at_i>{time_filters[time_range]}"

        async with httpx.AsyncClient() as client:
            response = await client.get(base_url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        results = []

        for hit in data.get("hits", [])[:max_results]:
            # Calculate relevance score
            relevance_score = calculate_hn_relevance(hit, topic, content_type)

            result = {
                "id": hit.get("objectID", ""),
                "title": hit.get("title", ""),
                "url": hit.get("url", ""),
                "hn_url": f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
                "points": hit.get("points", 0),
                "num_comments": hit.get("num_comments", 0),
                "author": hit.get("author", ""),
                "created_at": hit.get("created_at", ""),
                "relevance_score": relevance_score,
                "content_type": content_type if content_type != "any" else "discussion",
                "type": "hackernews_discussion",
            }

            results.append(result)

        # Sort by relevance score
        results.sort(key=lambda x: x["relevance_score"], reverse=True)

        logger.info("Found %d HackerNews discussions for topic: %s", len(results), topic)

        return {
            "results": results,
            "total_found": len(results),
            "search_query": query,
            "filters_applied": {
                "content_type": content_type,
                "time_range": time_range,
                "min_points": min_points
            },
        }

    except Exception as e:
        logger.exception("Error searching HackerNews")
        return {
            "results": [],
            "total_found": 0,
            "search_query": topic,
            "error": f"HackerNews search failed: {e!s}",
        }


def calculate_hn_relevance(hit: dict[str, Any], topic: str, content_type: str) -> float:
    """Calculate relevance score for a HackerNews post."""
    score = 0.0

    title = hit.get("title", "").lower()

    # Topic matching in title (40% weight)
    topic_words = topic.lower().split()
    for word in topic_words:
        if word in title:
            score += 0.4 / len(topic_words)

    # Content type keywords (20% weight)
    if content_type != "any":
        type_keywords = {
            "tutorial": ["tutorial", "guide", "how", "learn", "introduction"],
            "discussion": ["ask hn", "discussion", "thoughts", "opinions"],
            "resource": ["awesome", "collection", "resources", "list"],
            "tool": ["tool", "library", "framework", "released"],
        }

        for keyword in type_keywords.get(content_type, []):
            if keyword in title:
                score += 0.2

    # Points and engagement scoring (40% weight)
    points = hit.get("points", 0)
    comments = hit.get("num_comments", 0)

    if points > 100:
        score += 0.2
    elif points > 50:
        score += 0.1

    if comments > 50:
        score += 0.2
    elif comments > 20:
        score += 0.1

    return min(score, 1.0)
