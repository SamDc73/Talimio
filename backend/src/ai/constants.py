"""Shared AI constants."""

# Logical agent identifiers used to scope AI callers per module.
AGENT_ID_DEFAULT = "llm-client"
AGENT_ID_COURSE_PLANNER = "course-planner"
AGENT_ID_ASSISTANT = "assistant"
AGENT_ID_LESSON_WRITER = "lesson-writer"


__all__ = [
    "AGENT_ID_ASSISTANT",
    "AGENT_ID_COURSE_PLANNER",
    "AGENT_ID_DEFAULT",
    "AGENT_ID_LESSON_WRITER",
]
