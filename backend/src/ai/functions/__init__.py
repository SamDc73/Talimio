"""AI Functions module for function calling.

This module provides function calling capabilities for AI models.
"""

# Import all search functions to register them
from . import hackernews_search, internal_search, web_search, youtube_search
from .registry import (
    clear_registry,
    execute_function,
    get_function_info,
    get_function_names,
    get_function_schemas,
    get_registry_status,
    register_function,
)


def select_functions_for_task(task_type: str, _topic: str | None = None) -> list:
    """Select appropriate functions based on task type."""
    import os

    if task_type == "roadmap_creation":
        # Always include all content discovery functions for roadmap creation
        return [
            "search_internal_library",
            "search_youtube_videos",
            "search_hackernews_discussions",
            "search_web_content",
        ]
    if task_type == "lesson_generation":
        # Include all content discovery functions for lesson generation
        return [
            "search_youtube_videos",
            "search_web_content",
            "search_hackernews_discussions",
            "search_internal_library",
        ]

    return []


def get_roadmap_functions(topic: str | None = None) -> list:
    """Get all content discovery functions for roadmap creation."""
    function_names = select_functions_for_task("roadmap_creation", topic)
    all_functions = get_function_schemas()
    return [f for f in all_functions if f["name"] in function_names]


def get_lesson_functions(topic: str | None = None) -> list:
    """Get content discovery functions for lesson generation."""
    function_names = select_functions_for_task("lesson_generation", topic)
    all_functions = get_function_schemas()
    return [f for f in all_functions if f["name"] in function_names]


__all__ = [
    "clear_registry",
    "execute_function",
    "get_function_info",
    "get_function_names",
    "get_function_schemas",
    "get_lesson_functions",
    "get_registry_status",
    "get_roadmap_functions",
    "register_function",
    "select_functions_for_task",
]
