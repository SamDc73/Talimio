"""AI module initialization and configuration."""

from typing import Any, cast

import litellm


# Configure LiteLLM at module initialization
litellm.enable_json_schema_validation = True
litellm.drop_params = True
# LiteLLM exposes suppress_debug_info as Literal[False]; cast avoids false-positive type errors
cast("Any", litellm).suppress_debug_info = True  # Reduce verbose logging

# Logical agent identifiers used for mem0 scoping
AGENT_ID_DEFAULT = "llm-client"
AGENT_ID_COURSE_PLANNER = "course-planner"
AGENT_ID_ASSISTANT = "assistant"
AGENT_ID_LESSON_WRITER = "lesson-writer"
