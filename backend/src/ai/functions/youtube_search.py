"""YouTube video search functionality.

This module handles YouTube video search and discovery for educational content.
"""

import asyncio
import json
import logging
from typing import Any

from .registry import register_function


logger = logging.getLogger(__name__)


@register_function(
    {
        "type": "function",
        "name": "search_youtube_videos",
        "description": "Search YouTube videos with smart result count and duration filtering",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query for YouTube"},
                "search_count": {"type": "integer", "description": "Number of results to search for (overrides smart calculation)"},
                "desired_count": {"type": "integer", "description": "Number of videos you want after filtering (used for smart search count)"},
                "min_duration": {"type": "integer", "description": "Minimum video duration in seconds"},
                "max_duration": {"type": "integer", "description": "Maximum video duration in seconds"},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "strict": True,
    }
)
async def search_youtube_videos(
    query: str,
    search_count: int | None = None,
    desired_count: int | None = None,
    min_duration: int | None = None,
    max_duration: int | None = None,
) -> dict[str, Any]:
    """Search YouTube videos using yt-dlp with smart filtering.

    Args:
        query: Search query for YouTube
        search_count: Number of results to search for (overrides smart calculation)
        desired_count: Number of videos you want after filtering
        min_duration: Minimum video duration in seconds
        max_duration: Maximum video duration in seconds

    Returns
    -------
        Dictionary with search results and metadata
    """
    # Smart search count calculation
    if search_count is None:
        search_count = _calculate_smart_search_count(desired_count)

    logger.info("Searching YouTube for: %s (fetching %d results)", query, search_count)

    # Build yt-dlp command
    cmd = _build_ytdlp_command(query, search_count, min_duration, max_duration)

    try:
        # Run yt-dlp subprocess
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.error("yt-dlp failed: %s", error_msg)
            return _create_youtube_error_response(query, f"yt-dlp failed: {error_msg}")

        # Parse JSON output (one JSON object per line)
        videos = _parse_ytdlp_output(stdout.decode())

        logger.info("Found %d videos for query: %s", len(videos), query)

        return {
            "success": True,
            "videos": videos,
            "total_found": len(videos),
            "search_query": query,
            "search_count": search_count,
            "filters": {
                "min_duration": min_duration,
                "max_duration": max_duration,
            }
        }

    except Exception as e:
        logger.exception("Error running yt-dlp")
        return _create_youtube_error_response(query, f"Failed to run yt-dlp: {e!s}")


def _calculate_smart_search_count(desired_count: int | None) -> int:
    """Calculate smart search count based on desired results."""
    if desired_count:
        # Use multiplier that decreases as desired count increases
        multiplier = 2.5 - (min(desired_count, 30) * 0.05)
        return max(10, int(desired_count * multiplier))
    return 10  # Default


def _build_ytdlp_command(
    query: str, search_count: int, min_duration: int | None, max_duration: int | None
) -> list[str]:
    """Build yt-dlp command with appropriate filters."""
    cmd = [
        "yt-dlp",
        f"ytsearch{search_count}:{query}",
        "--skip-download",
        "--no-check-formats",
        "--ignore-errors",
        "--quiet",  # Suppress progress output
        "--no-warnings",
        "--print", "%(.{id,title,description,channel,duration,chapters,view_count,like_count,channel_follower_count,upload_date})j",
    ]

    # Add duration filter if specified
    if min_duration is not None or max_duration is not None:
        filter_parts = []
        if min_duration is not None:
            filter_parts.append(f"duration >= {min_duration}")
        if max_duration is not None:
            filter_parts.append(f"duration <= {max_duration}")
        cmd.extend(["--match-filter", " & ".join(filter_parts)])

    return cmd


def _parse_ytdlp_output(output: str) -> list[dict[str, Any]]:
    """Parse yt-dlp JSON output into video list."""
    videos = []
    for line in output.strip().split("\n"):
        if line:
            try:
                video = json.loads(line)
                videos.append(video)
            except json.JSONDecodeError:
                logger.warning("Failed to parse video JSON: %s", line)
                continue
    return videos


def _create_youtube_error_response(query: str, error_message: str) -> dict[str, Any]:
    """Create standardized error response for YouTube search."""
    return {
        "success": False,
        "videos": [],
        "total_found": 0,
        "search_query": query,
        "error": error_message
    }
