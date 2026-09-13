"""Instructor question bank for question-bank courses: the course's canon.

Inserts the bank (``course_questions``) at creation, maps it onto the derived
concept graph inside the outline job, and reads it back with the learner's
attempt stats. Serving the bank to a learner lives in
``question_bank_practice_service``.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.models import QuestionConceptAssignment
from src.courses.models import Concept, CourseConcept, CourseQuestion
from src.courses.schemas import (
    CourseQuestionCreate,
    CourseQuestionRead,
    PracticeAnswerKind,
    QuestionBankResponse,
    QuestionFigure,
    UncoveredConcept,
)
from src.courses.services.question_bank_practice_service import (
    AttemptHistory,
    QuestionBankPracticeService,
    bank_source_key,
)


class QuestionBankService:
    """Own the instructor bank rows for one course."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert_questions(
        self,
        *,
        course_id: uuid.UUID,
        questions: Sequence[CourseQuestionCreate],
    ) -> list[CourseQuestion]:
        """Store the instructor's questions in author order; concepts are mapped later by the outline job."""
        rows = [
            CourseQuestion(
                course_id=course_id,
                position=position,
                question=item.question.strip(),
                expected_answer=item.expected_answer.strip(),
                answer_kind=item.answer_kind,
                choices=item.choices,
                hints=item.hints,
                figure=item.figure.model_dump() if item.figure else None,
            )
            for position, item in enumerate(questions)
        ]
        self._session.add_all(rows)
        await self._session.flush()
        return rows

    async def list_questions(self, course_id: uuid.UUID) -> list[CourseQuestion]:
        """Return the bank in author order."""
        result = await self._session.execute(
            select(CourseQuestion).where(CourseQuestion.course_id == course_id).order_by(CourseQuestion.position)
        )
        return list(result.scalars().all())

    @staticmethod
    def build_prompt_block(questions: Sequence[CourseQuestion]) -> str:
        """Render the bank as the numbered list the structuring prompt expects (answers included so grouping is accurate)."""
        lines: list[str] = [
            f"{len(questions)} questions, numbered 0 to {len(questions) - 1}. Assign every one of them."
        ]
        for index, item in enumerate(questions):
            lines.append(f"{index}. [{item.answer_kind}] {item.question}")
            if item.choices:
                lines.append(f"   choices: {' | '.join(item.choices)}")
            lines.append(f"   expected: {item.expected_answer}")
        return "\n".join(lines)

    async def assign_concepts(
        self,
        *,
        questions: Sequence[CourseQuestion],
        concepts_by_index: Sequence[Concept],
        assignments: Sequence[QuestionConceptAssignment],
    ) -> None:
        """Point every bank question at its derived concept; a missing assignment fails the job."""
        concept_index_by_question = {item.question_index: item.concept_index for item in assignments}
        for question_index, question in enumerate(questions):
            concept_index = concept_index_by_question.get(question_index)
            if concept_index is None:
                message = f"Question {question_index} was not assigned to a concept"
                raise ValueError(message)
            question.concept_id = concepts_by_index[concept_index].id
        await self._session.flush()

    async def get_question_bank(self, *, course_id: uuid.UUID, user_id: uuid.UUID) -> QuestionBankResponse:
        """Bank rows with mapped concept names, this learner's attempt stats, and uncovered graph concepts."""
        questions = await self.list_questions(course_id)
        concept_names = await self._concept_names_for_course(course_id)
        history_by_source_key = await QuestionBankPracticeService(self._session).attempt_history_by_source_key(
            course_id=course_id, user_id=user_id
        )

        items: list[CourseQuestionRead] = []
        for question in questions:
            history = history_by_source_key.get(bank_source_key(question.id), AttemptHistory())
            items.append(
                CourseQuestionRead(
                    id=question.id,
                    position=question.position,
                    question=question.question,
                    answer_kind=_answer_kind(question.answer_kind),
                    choices=question.choices,
                    hints=question.hints,
                    figure=QuestionFigure.model_validate(question.figure) if question.figure else None,
                    concept_id=question.concept_id,
                    concept_name=concept_names.get(question.concept_id) if question.concept_id else None,
                    attempts=history.attempts,
                    correct_attempts=history.correct_attempts,
                )
            )

        covered_concept_ids = {question.concept_id for question in questions if question.concept_id is not None}
        uncovered = [
            UncoveredConcept(id=concept_id, name=name)
            for concept_id, name in concept_names.items()
            if concept_id not in covered_concept_ids
        ]
        return QuestionBankResponse(questions=items, uncovered_concepts=uncovered)

    async def _concept_names_for_course(self, course_id: uuid.UUID) -> dict[uuid.UUID, str]:
        rows = await self._session.execute(
            select(Concept.id, Concept.name)
            .join(CourseConcept, CourseConcept.concept_id == Concept.id)
            .where(CourseConcept.course_id == course_id)
            .order_by(CourseConcept.order_hint, Concept.name)
        )
        return dict(rows.tuples().all())


def _answer_kind(value: str) -> PracticeAnswerKind:
    if value == "latex":
        return "latex"
    if value == "choice":
        return "choice"
    return "text"
