"""Share links: mint one for an owned course, preview it, and fork the course for whoever redeems it.

A fork copies only the course's backbone (the row, its concept links, and the
instructor bank) and reuses the same concept nodes, so the recipient starts
with zero mastery on exactly the graph the author built. Learner state
(``learning_questions``, ``user_concept_state``, ``probe_events``) never travels.
"""

import logging
import secrets
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import get_settings
from src.courses.models import Concept, Course, CourseConcept, CourseQuestion, CourseShare
from src.courses.schemas import CourseSharePreview, CourseShareResponse
from src.exceptions import BadRequestError, ConflictError, NotFoundError


logger = logging.getLogger(__name__)


class CourseShareService:
    """Own the course_shares rows and the fork they unlock."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_share(self, *, course_id: uuid.UUID, user_id: uuid.UUID) -> CourseShareResponse:
        """Mint a join link for an owned, ready question-bank course."""
        course = await self._owned_course(course_id, user_id)
        if course.mode != "question_bank":
            message = "Only question-bank courses can be shared for now"
            raise BadRequestError(message, feature_area="courses")
        if course.generation_status != "ready":
            message = "The course is still being prepared; share it once it is ready"
            raise ConflictError(message, feature_area="courses")

        share = CourseShare(course_id=course.id, token=secrets.token_urlsafe(16))
        self._session.add(share)
        await self._session.flush()
        logger.info("courses.share.created", extra={"course_id": str(course.id), "user_id": str(user_id)})
        return CourseShareResponse(token=share.token, url=self._join_url(share.token))

    async def get_preview(self, token: str) -> CourseSharePreview:
        """Title, size, and concept names of the shared course; the bank's answers stay server-side."""
        course = await self._shared_course(token)
        question_count = await self._session.scalar(
            select(func.count()).select_from(CourseQuestion).where(CourseQuestion.course_id == course.id)
        )
        concept_names = await self._session.scalars(
            select(Concept.name)
            .join(CourseConcept, CourseConcept.concept_id == Concept.id)
            .where(CourseConcept.course_id == course.id)
            .order_by(CourseConcept.order_hint, Concept.name)
        )
        return CourseSharePreview(
            title=course.title,
            description=course.description,
            mode=course.mode,
            question_count=question_count or 0,
            concept_names=list(concept_names.all()),
        )

    async def fork(self, *, token: str, user_id: uuid.UUID) -> Course:
        """Copy the shared course's backbone into a new course owned by ``user_id``."""
        source = await self._shared_course(token)
        copy = Course(
            user_id=user_id,
            title=source.title,
            description=source.description,
            tags=source.tags,
            setup_commands=source.setup_commands,
            adaptive_enabled=source.adaptive_enabled,
            mode=source.mode,
            forked_from_course_id=source.id,
            generation_status="ready",
        )
        self._session.add(copy)
        await self._session.flush()

        # Same concept nodes, so prerequisites and confusors are already in place.
        links = await self._session.scalars(select(CourseConcept).where(CourseConcept.course_id == source.id))
        copied_links = [
            CourseConcept(course_id=copy.id, concept_id=link.concept_id, order_hint=link.order_hint) for link in links
        ]
        self._session.add_all(copied_links)

        questions = await self._session.scalars(
            select(CourseQuestion).where(CourseQuestion.course_id == source.id).order_by(CourseQuestion.position)
        )
        copied_questions = [
            CourseQuestion(
                course_id=copy.id,
                concept_id=question.concept_id,
                position=question.position,
                question=question.question,
                expected_answer=question.expected_answer,
                answer_kind=question.answer_kind,
                choices=question.choices,
                hints=question.hints,
                figure=question.figure,
            )
            for question in questions
        ]
        self._session.add_all(copied_questions)
        await self._session.flush()
        logger.info(
            "courses.share.forked",
            extra={"source_course_id": str(source.id), "course_id": str(copy.id), "user_id": str(user_id)},
        )
        return copy

    async def _owned_course(self, course_id: uuid.UUID, user_id: uuid.UUID) -> Course:
        course = await self._session.scalar(select(Course).where(Course.id == course_id, Course.user_id == user_id))
        if course is None:
            resource_type = "course"
            raise NotFoundError(resource_type, str(course_id), feature_area="courses")
        return course

    async def _shared_course(self, token: str) -> Course:
        course = await self._session.scalar(
            select(Course).join(CourseShare, CourseShare.course_id == Course.id).where(CourseShare.token == token)
        )
        if course is None:
            resource_type = "course share"
            raise NotFoundError(resource_type, feature_area="courses")
        return course

    @staticmethod
    def _join_url(token: str) -> str:
        return f"{get_settings().frontend_app_url.rstrip('/')}/#/join/{token}"
