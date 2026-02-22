"""Shared casing helpers for API schema serialization."""

from typing import Any

from pydantic import ConfigDict


def to_camel(field_name: str) -> str:
    """Convert snake_case field names to camelCase API aliases."""
    parts = field_name.split("_")
    if len(parts) == 1:
        return field_name
    head, *tail = parts
    return head + "".join(part.capitalize() for part in tail)


def build_camel_config(**overrides: Any) -> ConfigDict:
    """Build a consistent camelCase Pydantic config."""
    return ConfigDict(alias_generator=to_camel, populate_by_name=True, **overrides)
