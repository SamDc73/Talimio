"""Learner-facing pedagogical memory endpoints (inspect / suppress / forget)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from src.auth import CurrentAuth
from src.config.schema_casing import build_camel_config
from src.courses.models import Course
from src.exceptions import NotFoundError
from src.memory.pedagogy_controls import (
    forget_pedagogical_memory,
    get_pedagogical_memory,
    suppress_claim,
)


router = APIRouter(
    prefix="/api/v1/courses/{course_id}/memory",
    tags=["pedagogical-memory"],
)


async def valid_owned_course(course_id: uuid.UUID, auth: CurrentAuth) -> Course:
    """Load the course only when the current user owns it; 404 otherwise."""
    course = await auth.session.scalar(select(Course).where(Course.id == course_id, Course.user_id == auth.user_id))
    if course is None:
        resource_type = "Course"
        raise NotFoundError(resource_type, str(course_id))
    return course


OwnedCourse = Annotated[Course, Depends(valid_owned_course)]


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


@router.get("")
async def inspect_pedagogical_memory(auth: CurrentAuth, course: OwnedCourse) -> PedagogicalMemoryResponse:
    """Show the teaching profile (with sources) and the card claims with provenance."""
    view = await get_pedagogical_memory(auth.session, user_id=auth.user_id, course_id=course.id)
    return PedagogicalMemoryResponse(
        teaching_profile=[
            TeachingProfileFieldSchema(name=item.name, value=item.value, source=item.source)
            for item in view.teaching_profile
        ],
        avoid_list=view.avoid_list,
        card_text=view.card_text,
        card_revision=view.card_revision,
        card_updated_at=view.card_updated_at,
        claims=view.claims,
    )


@router.post("/claims/suppress")
async def suppress_pedagogical_claim(
    auth: CurrentAuth, course: OwnedCourse, request: SuppressClaimRequest
) -> SuppressClaimResponse:
    """Remove one claim line from the student card; measured outcomes stay."""
    revision = await suppress_claim(
        auth.session, user_id=auth.user_id, course_id=course.id, claim_text=request.claim_text
    )
    return SuppressClaimResponse(revision=revision)


@router.delete("")
async def forget_course_pedagogical_memory(auth: CurrentAuth, course: OwnedCourse) -> ForgetMemoryResponse:
    """Forget this course's pedagogical memory; evidence redaction cascades async."""
    await forget_pedagogical_memory(auth.session, user_id=auth.user_id, course_id=course.id)
    return ForgetMemoryResponse()
