"""API schemas for the learner-facing pedagogical memory endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from src.config.schema_casing import CamelModel


class TeachingProfileFieldSchema(CamelModel):
    """One merged teaching-profile field with its provenance source."""

    name: str
    value: str
    source: Literal["explicit", "inferred"]


class PedagogicalMemoryResponse(CamelModel):
    """Everything pedagogical memory knows about this learner-course pair."""

    teaching_profile: list[TeachingProfileFieldSchema]
    avoid_list: list[str]
    card_text: str | None
    card_revision: int | None
    card_updated_at: datetime | None
    claims: dict[str, list[str]]


class SuppressClaimRequest(CamelModel):
    """One verbatim claim line to remove from the student card."""

    claim_text: str


class SuppressClaimResponse(CamelModel):
    """Card revision after a successful suppression."""

    revision: int


class ForgetMemoryResponse(CamelModel):
    """Acknowledgement of an explicit pedagogical-memory forget."""

    status: Literal["forgotten"] = "forgotten"
