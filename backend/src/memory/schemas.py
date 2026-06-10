"""API schemas for the learner-facing pedagogical memory endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from src.config.schema_casing import build_camel_config


class TeachingProfileFieldSchema(BaseModel):
    """One merged teaching-profile field with its provenance source."""

    model_config = build_camel_config()

    name: str
    value: str
    source: str


class PedagogicalMemoryResponse(BaseModel):
    """Everything pedagogical memory knows about this learner-course pair."""

    model_config = build_camel_config()

    teaching_profile: list[TeachingProfileFieldSchema]
    avoid_list: list[str]
    card_text: str | None
    card_revision: int | None
    card_updated_at: datetime | None
    claims: dict[str, list[str]]


class SuppressClaimRequest(BaseModel):
    """One verbatim claim line to remove from the student card."""

    model_config = build_camel_config()

    claim_text: str


class SuppressClaimResponse(BaseModel):
    """Card revision after a successful suppression."""

    model_config = build_camel_config()

    revision: int


class ForgetMemoryResponse(BaseModel):
    """Acknowledgement of an explicit pedagogical-memory forget."""

    model_config = build_camel_config()

    status: str = "forgotten"
