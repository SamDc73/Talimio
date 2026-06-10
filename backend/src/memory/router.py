"""Learner-facing pedagogical memory endpoints (inspect / suppress / forget)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from src.auth import CurrentAuth
from src.courses.models import Course
from src.exceptions import NotFoundError
from src.memory.schemas import (
    ForgetMemoryResponse,
    PedagogicalMemoryResponse,
    SuppressClaimRequest,
    SuppressClaimResponse,
    TeachingProfileFieldSchema,
)
from src.memory.services.pedagogy_controls import (
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
