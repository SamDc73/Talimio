"""Unified internal error taxonomy for LLM runtime failures."""

from __future__ import annotations

from enum import Enum


class AIRuntimeErrorCategory(str, Enum):
    """Stable categories used across the LLM runtime path."""

    RATE_LIMIT_OR_QUOTA = "rate_limit_or_quota"
    TIMEOUT = "timeout"
    SCHEMA_VALIDATION = "schema_validation"
    PROVIDER_FAILURE = "provider_failure"
    TOOL_EXECUTION = "tool_execution"


class AIRuntimeError(RuntimeError):
    """Base exception for all runtime failures produced by the LLM client."""

    def __init__(self, message: str, *, category: AIRuntimeErrorCategory) -> None:
        super().__init__(message)
        self.category = category


class AIRateLimitOrQuotaError(AIRuntimeError):
    """Raised when the provider reports quota exhaustion or rate limiting."""

    def __init__(self, message: str) -> None:
        super().__init__(message, category=AIRuntimeErrorCategory.RATE_LIMIT_OR_QUOTA)


class AITimeoutError(AIRuntimeError):
    """Raised when an LLM runtime operation exceeds timeout."""

    def __init__(self, message: str) -> None:
        super().__init__(message, category=AIRuntimeErrorCategory.TIMEOUT)


class AISchemaValidationError(AIRuntimeError):
    """Raised when structured output fails schema validation."""

    def __init__(self, message: str) -> None:
        super().__init__(message, category=AIRuntimeErrorCategory.SCHEMA_VALIDATION)


class AIProviderError(AIRuntimeError):
    """Raised for generic provider-side runtime failures."""

    def __init__(self, message: str) -> None:
        super().__init__(message, category=AIRuntimeErrorCategory.PROVIDER_FAILURE)


class AIToolExecutionError(AIRuntimeError):
    """Raised when tool orchestration/execution fails at runtime."""

    def __init__(self, message: str) -> None:
        super().__init__(message, category=AIRuntimeErrorCategory.TOOL_EXECUTION)
