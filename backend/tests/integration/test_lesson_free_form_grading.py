# ruff: noqa: S101, ANN001, ANN002, ANN003, ANN202, RUF029, S106

"""Integration coverage for lesson free-form grading through server-owned attempts."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.courses.models import Concept, Course, CourseConcept, LearningQuestion, Lesson
from src.courses.services.grading_service import LLMGradeFeedback
from src.user.models import User
from tests.fixtures.auth_modes import AuthMode


async def _create_course_question(
    test_engine,
    *,
    owner_id: uuid.UUID,
    course_id: uuid.UUID,
    lesson_id: uuid.UUID,
    concept_id: uuid.UUID,
    question_id: uuid.UUID,
    question: str,
    expected_answer: str,
    answer_kind: str,
) -> None:
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        existing_user = await session.scalar(select(User.id).where(User.id == owner_id))
        if existing_user is None:
            session.add(
                User(
                    id=owner_id,
                    username=f"lesson-free-form-{str(owner_id)[:8]}",
                    email=f"lesson-free-form-{owner_id}@example.com",
                    password_hash="not-used-in-tests",
                )
            )
            await session.flush()

        session.add(
            Course(
                id=course_id,
                user_id=owner_id,
                title="Lesson Free Form Course",
                description="Course for lesson free-form grading integration coverage.",
                adaptive_enabled=True,
            )
        )
        session.add(
            Lesson(
                id=lesson_id,
                course_id=course_id,
                title="Lesson Free Form Lesson",
                description="Lesson tied to free-form grading integration coverage.",
                content="## Reflection",
                order=1,
            )
        )
        session.add(
            Concept(
                id=concept_id,
                domain="stem",
                slug=f"lesson-free-form-{course_id}",
                name="Lesson Free Form Concept",
                description="Concept used for lesson free-form grading integration coverage.",
            )
        )
        session.add(CourseConcept(course_id=course_id, concept_id=concept_id, order_hint=1))
        await session.flush()

        session.add(
            LearningQuestion(
                id=question_id,
                user_id=owner_id,
                course_id=course_id,
                concept_id=concept_id,
                lesson_id=lesson_id,
                question=question,
                expected_answer=expected_answer,
                answer_kind=answer_kind,
                grade_kind="practice_answer",
                expected_payload={},
                question_payload={"answerKind": answer_kind, "probeFamily": "free_recall", "rendererKind": "free_form"},
                hints=[],
                structure_signature=f"lesson-free-form:{question_id}",
                predicted_p_correct=0.5,
                target_probability=0.5,
                target_low=0.4,
                target_high=0.6,
                core_model="integration-test",
                practice_context="inline",
            )
        )
        await session.commit()


@pytest.mark.parametrize("auth_mode", [AuthMode.SINGLE_USER, AuthMode.MULTI_USER], indirect=True)
@pytest.mark.asyncio
async def test_lesson_free_form_attempt_grades_server_owned_text_question(
    auth_mode: AuthMode,
    client_factory,
    test_engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if auth_mode == AuthMode.SINGLE_USER:
        client = await client_factory()
    else:
        client = await client_factory("lesson-free-form@test.com")

    owner_id = uuid.UUID(client.expected_user_id)
    course_id = uuid.uuid4()
    lesson_id = uuid.uuid4()
    concept_id = uuid.uuid4()
    question_id = uuid.uuid4()
    await _create_course_question(
        test_engine,
        owner_id=owner_id,
        course_id=course_id,
        lesson_id=lesson_id,
        concept_id=concept_id,
        question_id=question_id,
        question="Why is caching useful in a web application?",
        expected_answer="Caching avoids repeated expensive work and lowers latency for repeated requests.",
        answer_kind="text",
    )

    async def mock_get_completion(*_args, **_kwargs):
        return LLMGradeFeedback(
            is_correct=False,
            status="incorrect",
            feedback_markdown="Good direction, but explain more clearly how caching avoids repeated work.",
            tags=["needs-specificity"],
        )

    monkeypatch.setattr("src.ai.client.LLMClient.get_completion", mock_get_completion)

    async with client:
        response = await client.post(
            f"/api/v1/courses/{course_id}/attempts",
            json={
                "attemptId": str(uuid.uuid4()),
                "questionId": str(question_id),
                "answer": {"kind": "text", "answerText": "It helps the app feel faster."},
                "hintsUsed": 0,
                "durationMs": 1200,
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["isCorrect"] is False
        assert body["status"] == "incorrect"
        assert body["feedbackMarkdown"] == "Good direction, but explain more clearly how caching avoids repeated work."
        assert body["exposures"] == 1
        assert "expectedAnswer" not in body


@pytest.mark.parametrize("auth_mode", [AuthMode.SINGLE_USER, AuthMode.MULTI_USER], indirect=True)
@pytest.mark.asyncio
async def test_lesson_free_form_attempt_grades_server_owned_math_question(
    auth_mode: AuthMode,
    client_factory,
    test_engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if auth_mode == AuthMode.SINGLE_USER:
        client = await client_factory()
    else:
        client = await client_factory("lesson-free-form-math@test.com")

    owner_id = uuid.UUID(client.expected_user_id)
    course_id = uuid.uuid4()
    lesson_id = uuid.uuid4()
    concept_id = uuid.uuid4()
    question_id = uuid.uuid4()
    await _create_course_question(
        test_engine,
        owner_id=owner_id,
        course_id=course_id,
        lesson_id=lesson_id,
        concept_id=concept_id,
        question_id=question_id,
        question="Expand $(x + 1)^2$.",
        expected_answer="x^2 + 2x + 1",
        answer_kind="latex",
    )

    async def mock_get_completion(*_args, **_kwargs):
        return LLMGradeFeedback(
            is_correct=True,
            status="correct",
            feedback_markdown="Correct. $x^2 + 2x + 1$ matches the expanded form.",
            tags=["expanded-form"],
        )

    monkeypatch.setattr("src.ai.client.LLMClient.get_completion", mock_get_completion)

    async with client:
        response = await client.post(
            f"/api/v1/courses/{course_id}/attempts",
            json={
                "attemptId": str(uuid.uuid4()),
                "questionId": str(question_id),
                "answer": {"kind": "latex", "answerText": "x^2 + 2x + 1"},
                "hintsUsed": 0,
                "durationMs": 900,
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["isCorrect"] is True
        assert body["status"] == "correct"
        assert body["feedbackMarkdown"] == "Correct. $x^2 + 2x + 1$ matches the expanded form."
        assert body["exposures"] == 1
        assert "expectedAnswer" not in body
