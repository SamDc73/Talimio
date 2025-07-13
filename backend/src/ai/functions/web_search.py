"""Web content search functionality.

This module handles web content search using Exa API for finding
high-quality educational resources from across the web.
"""

import logging
import os
from typing import Any

from .registry import register_function


logger = logging.getLogger(__name__)


@register_function(
    {
        "type": "function",
        "name": "search_web_content",
        "description": "Find educational web content using Exa AI search (documentation, tutorials, guides, articles)",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Learning topic to search for"},
                "content_type": {"type": "string", "enum": ["tutorial", "guide", "documentation", "blog", "any"]},
                "difficulty_level": {"type": "string", "enum": ["beginner", "intermediate", "advanced", "any"]},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 10},
            },
            "required": ["topic"],
            "additionalProperties": False,
        },
        "strict": True,
    }
)
async def search_web_content(
    topic: str,
    content_type: str = "any",
    difficulty_level: str = "any",
    max_results: int = 10,
) -> dict[str, Any]:
    """Search web content using Exa API for educational resources.

    Args:
        topic: Learning topic to search for
        content_type: Type of content (tutorial, guide, documentation, blog, any)
        difficulty_level: Target difficulty level (beginner, intermediate, advanced, any)
        max_results: Maximum number of results

    Returns
    -------
        Dictionary with web content search results
    """
    try:
        logger.info("Searching web content for topic: %s, type: %s", topic, content_type)

        exa_api_key = os.getenv("EXA_API_KEY")
        if not exa_api_key:
            logger.info("Exa API key not found, cannot perform web search")
            return {
                "results": [],
                "total_found": 0,
                "search_query": topic,
                "error": "Exa API key not configured",
            }

        from datetime import datetime, timedelta

        import exa_py

        client = exa_py.Exa(api_key=exa_api_key)

        # Build educational search query
        query_parts = [topic]

        # Add content type qualifiers
        if content_type != "any":
            if content_type == "tutorial":
                query_parts.extend(["tutorial", "guide", "how to"])
            elif content_type == "guide":
                query_parts.extend(["complete guide", "comprehensive", "step by step"])
            elif content_type == "documentation":
                query_parts.extend(["documentation", "docs", "reference"])
            elif content_type == "blog":
                query_parts.extend(["blog", "article", "post"])

        # Add difficulty qualifiers
        if difficulty_level != "any":
            if difficulty_level == "beginner":
                query_parts.extend(["beginner", "introduction", "getting started"])
            elif difficulty_level == "intermediate":
                query_parts.extend(["intermediate", "advanced concepts"])
            elif difficulty_level == "advanced":
                query_parts.extend(["advanced", "expert", "deep dive"])

        query = " ".join(query_parts)

        # Set date filters for recent content
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)  # Last year

        # Perform search with content retrieval
        response = client.search_and_contents(
            query,
            num_results=max_results,
            use_autoprompt=True,  # Exa will optimize the query
            type="neural",  # Use neural search for better semantic matching
            text={"max_characters": 1000},  # Get text preview
            highlights=True,  # Get relevant highlights
            start_published_date=start_date.strftime("%Y-%m-%d"),
            end_published_date=end_date.strftime("%Y-%m-%d"),
            include_domains=[  # Focus on educational domains
                "medium.com",
                "dev.to",
                "towardsdatascience.com",
                "realpython.com",
                "freecodecamp.org",
                "hackernoon.com",
                "css-tricks.com",
                "smashingmagazine.com",
                "docs.python.org",
                "developer.mozilla.org",
                "w3schools.com",
                "geeksforgeeks.org",
                "stackoverflow.com",
                "github.com",
                "arxiv.org",
            ],
        )

        results = []
        for result in response.results:
            # Calculate relevance score
            relevance_score = calculate_relevance(result, topic, content_type, difficulty_level)

            content_result = {
                "title": result.title,
                "url": result.url,
                "text_preview": result.text[:500] + "..." if result.text else "",
                "highlights": result.highlights if hasattr(result, "highlights") else [],
                "score": result.score,
                "published_date": result.published_date,
                "author": result.author if hasattr(result, "author") else None,
                "relevance_score": relevance_score,
                "source": "exa",
                "type": "web_content",
                "content_type": content_type if content_type != "any" else "unknown",
                "difficulty_level": difficulty_level if difficulty_level != "any" else "unknown",
            }

            results.append(content_result)

        # Sort by relevance score
        results.sort(key=lambda x: x["relevance_score"], reverse=True)

        logger.info("Found %d web content items for topic: %s", len(results), topic)

        return {
            "results": results,
            "total_found": len(results),
            "search_query": query,
            "filters_applied": {
                "content_type": content_type,
                "difficulty_level": difficulty_level,
            },
        }

    except ImportError:
        logger.warning("exa-py library not installed. Install with: pip install exa-py")
        return {
            "results": [],
            "total_found": 0,
            "search_query": topic,
            "error": "exa-py library not installed",
        }
    except Exception as e:
        logger.exception("Error searching web content")
        return {
            "results": [],
            "total_found": 0,
            "search_query": topic,
            "error": f"Web content search failed: {e!s}",
        }


def calculate_relevance(result: Any, topic: str, content_type: str, difficulty: str) -> float:
    """Calculate relevance score for Exa search result."""
    # Start with Exa's own score (already normalized 0-1)
    score = result.score * 0.5  # Give 50% weight to Exa's score

    title = result.title.lower() if result.title else ""
    text = result.text.lower() if hasattr(result, "text") and result.text else ""

    # Topic matching (25% weight)
    topic_words = topic.lower().split()
    topic_matches = sum(1 for word in topic_words if word in title or word in text[:500])
    score += (topic_matches / len(topic_words)) * 0.25

    # Content type matching (15% weight)
    if content_type != "any":
        type_keywords = {
            "tutorial": ["tutorial", "guide", "learn", "how to"],
            "guide": ["guide", "complete", "comprehensive"],
            "documentation": ["documentation", "reference", "api"],
            "blog": ["blog", "article", "post"],
        }

        type_matches = sum(
            1 for keyword in type_keywords.get(content_type, [])
            if keyword in title or keyword in text[:200]
        )
        score += min(type_matches * 0.05, 0.15)

    # Difficulty matching (10% weight)
    if difficulty != "any" and (difficulty in title or difficulty in text[:200]):
        score += 0.10

    return min(score, 1.0)
