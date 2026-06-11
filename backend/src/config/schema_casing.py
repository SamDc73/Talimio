"""Shared casing helpers for API schema serialization."""

from pydantic import BaseModel, ConfigDict


def to_camel(field_name: str) -> str:
    """Convert snake_case field names to camelCase API aliases."""
    parts = field_name.split("_")
    if len(parts) == 1:
        return field_name
    head, *tail = parts
    return head + "".join(part.capitalize() for part in tail)


class CamelModel(BaseModel):
    """Base for every HTTP API schema: snake_case in Python, camelCase on the wire."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
    )


def build_camel_config(**overrides: object) -> ConfigDict:
    """Build a camelCase Pydantic config for LLM structured-output models only.

    HTTP API schemas must inherit ``CamelModel`` instead; this helper remains
    solely for models whose camelCase aliases shape an LLM JSON contract.
    """
    return ConfigDict(alias_generator=to_camel, populate_by_name=True, **overrides)
