# ruff: noqa: S101, ANN001, ANN002, ANN003, ANN202, RUF029, S106

"""Integration coverage for Adaptive Practice server-owned attempts."""

import json
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.errors import AIProviderError
from src.courses.models import (
    Concept,
    Course,
    CourseConcept,
    LearningAttempt,
    LearningQuestion,
    Lesson,
    ProbeEvent,
    UserConceptState,
)
from src.courses.schemas import PracticeDrillItem
from src.courses.services.grading_service import LLMGradeFeedback
from src.user.models import User
from tests.fixtures.auth_modes import AuthMode


async def _create_course_concept(
    test_engine,
    *,
    owner_id: uuid.UUID,
    course_id: uuid.UUID,
    lesson_id: uuid.UUID,
    concept_id: uuid.UUID,
) -> None:
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        existing_user = await session.scalar(select(User.id).where(User.id == owner_id))
        if existing_user is None:
            session.add(
                User(
                    id=owner_id,
                    username=f"adaptive-practice-{str(owner_id)[:8]}",
                    email=f"adaptive-practice-{owner_id}@example.com",
                    password_hash="not-used-in-tests",
                )
            )
            await session.flush()

        session.add(
            Course(
                id=course_id,
                user_id=owner_id,
                title="Adaptive Practice Course",
                description="Course for adaptive practice integration coverage.",
                adaptive_enabled=True,
            )
        )
        session.add(
            Lesson(
                id=lesson_id,
                course_id=course_id,
                title="Adaptive Practice Lesson",
                description="Lesson tied to adaptive practice integration coverage.",
                content="## Practice",
                order=1,
            )
        )
        session.add(
            Concept(
                id=concept_id,
                domain="stem",
                slug=f"adaptive-practice-{course_id}",
                name="Adaptive Practice Concept",
                description="Concept used for adaptive practice integration coverage.",
            )
        )
        session.add(CourseConcept(course_id=course_id, concept_id=concept_id, order_hint=1))
        await session.flush()
        await session.commit()


async def _create_course_question(
    test_engine,
    *,
    owner_id: uuid.UUID,
    course_id: uuid.UUID,
    lesson_id: uuid.UUID,
    concept_id: uuid.UUID,
    question_id: uuid.UUID,
    expected_answer: str = "5",
) -> None:
    await _create_course_concept(
        test_engine,
        owner_id=owner_id,
        course_id=course_id,
        lesson_id=lesson_id,
        concept_id=concept_id,
    )

    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        session.add(
            LearningQuestion(
                id=question_id,
                user_id=owner_id,
                course_id=course_id,
                concept_id=concept_id,
                lesson_id=lesson_id,
                question="Solve for x: x + 3 = 8",
                expected_answer=expected_answer,
                answer_kind="latex",
                grade_kind="practice_answer",
                expected_payload={},
                question_payload={"answerKind": "latex", "probeFamily": "free_recall", "rendererKind": "free_form"},
                hints=[],
                structure_signature=f"adaptive-practice:{question_id}",
                predicted_p_correct=0.5,
                target_probability=0.5,
                target_low=0.4,
                target_high=0.6,
                core_model="integration-test",
                practice_context="drill",
            )
        )
        await session.commit()


async def _post_attempt(client, *, course_id: uuid.UUID, question_id: uuid.UUID, answer: str, attempt_id: uuid.UUID | None = None):
    return await client.post(
        f"/api/v1/courses/{course_id}/attempts",
        json={
            "attemptId": str(attempt_id or uuid.uuid4()),
            "questionId": str(question_id),
            "answer": {"kind": "latex", "answerText": answer},
            "hintsUsed": 0,
            "durationMs": 1000,
        },
    )


@pytest.mark.parametrize("auth_mode", [AuthMode.SINGLE_USER, AuthMode.MULTI_USER], indirect=True)
@pytest.mark.asyncio
async def test_adaptive_practice_question_set_creates_hidden_server_owned_question(
    auth_mode: AuthMode,
    client_factory,
    test_engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if auth_mode == AuthMode.SINGLE_USER:
        client = await client_factory()
    else:
        client = await client_factory("adaptive-practice-question-set@test.com")

    owner_id = uuid.UUID(client.expected_user_id)
    course_id = uuid.uuid4()
    lesson_id = uuid.uuid4()
    concept_id = uuid.uuid4()
    await _create_course_concept(
        test_engine,
        owner_id=owner_id,
        course_id=course_id,
        lesson_id=lesson_id,
        concept_id=concept_id,
    )

    async def mock_generate_drills(*_args, **_kwargs):
        return [
            PracticeDrillItem(
                concept_id=concept_id,
                lesson_id=lesson_id,
                question="Solve for x: x + 3 = 8",
                expected_answer="5",
                answer_kind="latex",
                probe_family="free_recall",
                renderer_kind="free_form",
                choices=[],
                hints=["Subtract 3 from both sides."],
                structure_signature="question-set:hidden-answer",
                predicted_p_correct=0.5,
                target_probability=0.5,
                target_low=0.4,
                target_high=0.6,
                core_model="integration-test",
            )
        ]

    async def mock_get_completion(*_args, **_kwargs):
        return LLMGradeFeedback(
            is_correct=True,
            status="correct",
            feedback_markdown="Correct.",
            tags=["server-owned"],
        )

    monkeypatch.setattr("src.courses.services.practice_drill_service.PracticeDrillService.generate_drills", mock_generate_drills)
    monkeypatch.setattr("src.ai.client.LLMClient.get_completion", mock_get_completion)

    async with client:
        question_set = await client.post(
            f"/api/v1/courses/{course_id}/question-sets",
            json={
                "conceptId": str(concept_id),
                "count": 1,
                "practiceContext": "drill",
                "lessonId": str(lesson_id),
            },
        )
        assert question_set.status_code == 200, question_set.text
        body = question_set.json()
        assert "expectedAnswer" not in str(body)
        question = body["questions"][0]
        assert question["question"] == "Solve for x: x + 3 = 8"
        assert question["answerKind"] == "latex"
        assert question["hints"] == ["Subtract 3 from both sides."]

        response = await _post_attempt(
            client,
            course_id=course_id,
            question_id=uuid.UUID(question["questionId"]),
            answer="5",
        )
        assert response.status_code == 200, response.text
        assert response.json()["isCorrect"] is True

    async with AsyncSession(test_engine, expire_on_commit=False) as verify_session:
        stored_question = await verify_session.get(LearningQuestion, uuid.UUID(question["questionId"]))
        assert stored_question is not None
        assert stored_question.expected_payload == {}


@pytest.mark.parametrize("auth_mode", [AuthMode.SINGLE_USER, AuthMode.MULTI_USER], indirect=True)
@pytest.mark.asyncio
async def test_adaptive_practice_attempt_uses_llm_contract(
    auth_mode: AuthMode,
    client_factory,
    test_engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if auth_mode == AuthMode.SINGLE_USER:
        client = await client_factory()
    else:
        client = await client_factory("adaptive-practice-grade@test.com")

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
    )

    async def mock_get_completion(*_args, **_kwargs):
        return LLMGradeFeedback(
            is_correct=True,
            status="correct",
            feedback_markdown="Nice work. Your answer matches the expected result.",
            tags=["simplification"],
        )

    monkeypatch.setattr("src.ai.client.LLMClient.get_completion", mock_get_completion)

    async with client:
        response = await _post_attempt(client, course_id=course_id, question_id=question_id, answer="5")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["isCorrect"] is True
        assert body["status"] == "correct"
        assert body["feedbackMarkdown"] == "Nice work. Your answer matches the expected result."
        assert set(body) >= {"attemptId", "isCorrect", "status", "feedbackMarkdown", "mastery", "exposures", "nextReviewAt"}
        assert "expectedAnswer" not in body


@pytest.mark.parametrize("auth_mode", [AuthMode.SINGLE_USER, AuthMode.MULTI_USER], indirect=True)
@pytest.mark.asyncio
async def test_adaptive_practice_attempt_requires_matching_answer_kind(
    auth_mode: AuthMode,
    client_factory,
    test_engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if auth_mode == AuthMode.SINGLE_USER:
        client = await client_factory()
    else:
        client = await client_factory("adaptive-practice-answer-kind@test.com")

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
    )

    async def mock_get_completion(*_args, **_kwargs):
        detail = "grading should not run for an answer-kind mismatch"
        raise AssertionError(detail)

    monkeypatch.setattr("src.ai.client.LLMClient.get_completion", mock_get_completion)

    async with client:
        response = await client.post(
            f"/api/v1/courses/{course_id}/attempts",
            json={
                "attemptId": str(uuid.uuid4()),
                "questionId": str(question_id),
                "answer": {"kind": "text", "answerText": "5"},
                "hintsUsed": 0,
                "durationMs": 1000,
            },
        )
        assert response.status_code == 422, response.text
        assert response.json()["error"]["detail"] == "Question expects a latex answer"


@pytest.mark.parametrize("auth_mode", [AuthMode.SINGLE_USER, AuthMode.MULTI_USER], indirect=True)
@pytest.mark.asyncio
async def test_adaptive_practice_legacy_routes_are_not_available(
    auth_mode: AuthMode,
    client_factory,
    test_engine,
) -> None:
    if auth_mode == AuthMode.SINGLE_USER:
        client = await client_factory()
    else:
        client = await client_factory("adaptive-practice-legacy-routes@test.com")

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
    )

    async with client:
        legacy_grade = await client.post(
            f"/api/v1/courses/{course_id}/lessons/{lesson_id}/grade",
            json={"answer": "5", "expectedAnswer": "5"},
        )
        assert legacy_grade.status_code == 404, legacy_grade.text

        legacy_reviews = await client.post(
            f"/api/v1/courses/{course_id}/lessons/{lesson_id}/reviews",
            json={"reviews": []},
        )
        assert legacy_reviews.status_code == 404, legacy_reviews.text

        legacy_drills = await client.post(
            f"/api/v1/courses/{course_id}/practice/drills",
            json={"conceptId": str(concept_id), "count": 1},
        )
        assert legacy_drills.status_code == 404, legacy_drills.text


@pytest.mark.parametrize("auth_mode", [AuthMode.SINGLE_USER, AuthMode.MULTI_USER], indirect=True)
@pytest.mark.asyncio
async def test_adaptive_practice_attempt_surfaces_llm_failures(
    auth_mode: AuthMode,
    client_factory,
    test_engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if auth_mode == AuthMode.SINGLE_USER:
        client = await client_factory()
    else:
        client = await client_factory("adaptive-practice-grade-fail@test.com")

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
    )

    async def mock_get_completion_failure(*_args, **_kwargs):
        detail = "simulated llm failure"
        raise AIProviderError(detail)

    monkeypatch.setattr("src.ai.client.LLMClient.get_completion", mock_get_completion_failure)

    async with client:
        response = await _post_attempt(client, course_id=course_id, question_id=question_id, answer="5")
        assert response.status_code == 503, response.text
        body = response.json()
        assert body["error"]["category"] == "UPSTREAM_UNAVAILABLE_ERROR"
        assert body["error"]["code"] == "UPSTREAM_UNAVAILABLE"
        assert body["error"]["detail"] == "Grading service is temporarily unavailable"


@pytest.mark.parametrize("auth_mode", [AuthMode.SINGLE_USER, AuthMode.MULTI_USER], indirect=True)
@pytest.mark.asyncio
async def test_adaptive_practice_attempt_maps_invalid_structured_output_to_upstream_unavailable(
    auth_mode: AuthMode,
    client_factory,
    test_engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if auth_mode == AuthMode.SINGLE_USER:
        client = await client_factory()
    else:
        client = await client_factory("adaptive-practice-invalid@test.com")

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
    )

    async def mock_get_completion_invalid(*_args, **_kwargs):
        return "not-a-structured-grade"

    monkeypatch.setattr("src.ai.client.LLMClient.get_completion", mock_get_completion_invalid)

    async with client:
        response = await _post_attempt(client, course_id=course_id, question_id=question_id, answer="5")
        assert response.status_code == 503, response.text
        body = response.json()
        assert body["error"]["category"] == "UPSTREAM_UNAVAILABLE_ERROR"
        assert body["error"]["code"] == "UPSTREAM_UNAVAILABLE"
        assert body["error"]["detail"] == "Grading service is temporarily unavailable"


@pytest.mark.parametrize("auth_mode", [AuthMode.SINGLE_USER, AuthMode.MULTI_USER], indirect=True)
@pytest.mark.asyncio
async def test_adaptive_practice_journey_updates_concept_state_through_attempts(
    auth_mode: AuthMode,
    client_factory,
    test_engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if auth_mode == AuthMode.SINGLE_USER:
        client = await client_factory()
    else:
        client = await client_factory("adaptive-practice-journey@test.com")

    owner_id = uuid.UUID(client.expected_user_id)
    course_id = uuid.uuid4()
    lesson_id = uuid.uuid4()
    concept_id = uuid.uuid4()
    first_question_id = uuid.uuid4()
    second_question_id = uuid.uuid4()
    await _create_course_question(
        test_engine,
        owner_id=owner_id,
        course_id=course_id,
        lesson_id=lesson_id,
        concept_id=concept_id,
        question_id=first_question_id,
    )

    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        first_question = await session.get(LearningQuestion, first_question_id)
        assert first_question is not None
        session.add(
            LearningQuestion(
                id=second_question_id,
                user_id=owner_id,
                course_id=course_id,
                concept_id=concept_id,
                lesson_id=lesson_id,
                question=first_question.question,
                expected_answer=first_question.expected_answer,
                answer_kind=first_question.answer_kind,
                grade_kind=first_question.grade_kind,
                expected_payload=first_question.expected_payload,
                question_payload=first_question.question_payload,
                hints=[],
                structure_signature=f"adaptive-practice:{second_question_id}",
                predicted_p_correct=0.5,
                target_probability=0.5,
                target_low=0.4,
                target_high=0.6,
                core_model="integration-test",
                practice_context="drill",
            )
        )
        await session.commit()

    async def mock_get_completion(*args, **kwargs):
        messages = kwargs.get("messages")
        if messages is None and len(args) > 1:
            messages = args[1]
        if messages is None:
            messages = []
        learner_payload = json.loads(messages[1]["content"]) if len(messages) > 1 else {}
        if learner_payload.get("learnerAnswer") == "4":
            return LLMGradeFeedback(
                is_correct=False,
                status="incorrect",
                feedback_markdown="Close, but re-check the arithmetic.",
                tags=["arithmetic-mistake"],
            )

        return LLMGradeFeedback(
            is_correct=True,
            status="correct",
            feedback_markdown="Nice recovery. Your updated answer is correct.",
            tags=["corrected-after-retry"],
        )

    monkeypatch.setattr("src.ai.client.LLMClient.get_completion", mock_get_completion)

    async with client:
        first_attempt = await _post_attempt(client, course_id=course_id, question_id=first_question_id, answer="4")
        assert first_attempt.status_code == 200, first_attempt.text
        first_body = first_attempt.json()
        assert first_body["isCorrect"] is False
        assert first_body["status"] == "incorrect"
        assert first_body["exposures"] == 1

        second_attempt = await _post_attempt(client, course_id=course_id, question_id=second_question_id, answer="5")
        assert second_attempt.status_code == 200, second_attempt.text
        second_body = second_attempt.json()
        assert second_body["isCorrect"] is True
        assert second_body["status"] == "correct"
        assert second_body["exposures"] == 2

    async with AsyncSession(test_engine, expire_on_commit=False) as verify_session:
        state = await verify_session.scalar(
            select(UserConceptState).where(
                UserConceptState.user_id == owner_id,
                UserConceptState.concept_id == concept_id,
            )
        )
        assert state is not None
        assert state.exposures == 2

        attempts_count = await verify_session.scalar(
            select(func.count()).select_from(LearningAttempt).where(LearningAttempt.user_id == owner_id)
        )
        assert attempts_count == 2

        probe_events_count = await verify_session.scalar(
            select(func.count()).select_from(ProbeEvent).where(ProbeEvent.user_id == owner_id)
        )
        assert probe_events_count == 2


@pytest.mark.parametrize("auth_mode", [AuthMode.SINGLE_USER, AuthMode.MULTI_USER], indirect=True)
@pytest.mark.asyncio
async def test_adaptive_practice_attempt_idempotency_prevents_duplicate_writeback(
    auth_mode: AuthMode,
    client_factory,
    test_engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if auth_mode == AuthMode.SINGLE_USER:
        client = await client_factory()
    else:
        client = await client_factory("adaptive-practice-idempotency@test.com")

    owner_id = uuid.UUID(client.expected_user_id)
    course_id = uuid.uuid4()
    lesson_id = uuid.uuid4()
    concept_id = uuid.uuid4()
    question_id = uuid.uuid4()
    attempt_id = uuid.uuid4()
    await _create_course_question(
        test_engine,
        owner_id=owner_id,
        course_id=course_id,
        lesson_id=lesson_id,
        concept_id=concept_id,
        question_id=question_id,
    )

    async def mock_get_completion(*_args, **_kwargs):
        return LLMGradeFeedback(
            is_correct=True,
            status="correct",
            feedback_markdown="Correct.",
            tags=["idempotent"],
        )

    monkeypatch.setattr("src.ai.client.LLMClient.get_completion", mock_get_completion)

    async with client:
        first = await _post_attempt(client, course_id=course_id, question_id=question_id, answer="5", attempt_id=attempt_id)
        assert first.status_code == 200, first.text
        duplicate = await _post_attempt(client, course_id=course_id, question_id=question_id, answer="5", attempt_id=attempt_id)
        assert duplicate.status_code == 200, duplicate.text
        assert duplicate.json() == first.json()

        conflict = await _post_attempt(client, course_id=course_id, question_id=question_id, answer="6", attempt_id=attempt_id)
        assert conflict.status_code == 409, conflict.text
        assert conflict.json()["error"]["code"] == "CONFLICT"

    async with AsyncSession(test_engine, expire_on_commit=False) as verify_session:
        state = await verify_session.scalar(
            select(UserConceptState).where(
                UserConceptState.user_id == owner_id,
                UserConceptState.concept_id == concept_id,
            )
        )
        assert state is not None
        assert state.exposures == 1

        attempts_count = await verify_session.scalar(
            select(func.count()).select_from(LearningAttempt).where(LearningAttempt.user_id == owner_id)
        )
        assert attempts_count == 1

        probe_events_count = await verify_session.scalar(
            select(func.count()).select_from(ProbeEvent).where(ProbeEvent.user_id == owner_id)
        )
        assert probe_events_count == 1
