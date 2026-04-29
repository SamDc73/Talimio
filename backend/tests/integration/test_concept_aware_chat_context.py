"""Phase 1 coverage for concept-aware assistant context packets."""

# ruff: noqa: S101

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai import client as ai_client
from src.ai.assistant.models import AssistantActiveProbe, AssistantConversation
from src.ai.assistant.schemas import ChatRequest
from src.ai.assistant.service import (
    _build_learning_environment_facts,  # noqa: PLC2701
    _build_learning_routing_packet,  # noqa: PLC2701
)
from src.ai.errors import AIProviderError
from src.ai.rag.schemas import SearchResult
from src.ai.tools.learning.action_tools import build_learning_action_tools
from src.ai.tools.learning.query_tools import build_learning_query_tools
from src.courses.models import (
    Concept,
    ConceptPrerequisite,
    ConceptSimilarity,
    Course,
    CourseConcept,
    CourseDocument,
    LearningQuestion,
    Lesson,
    LessonVersion,
    LessonVersionWindow,
    ProbeEvent,
    UserConceptState,
)
from src.courses.schemas import GradeResponse, PracticeDrillItem, VerifierInfo
from src.courses.services.practice_drill_service import PracticeDrillService
from src.exceptions import NotFoundError
from src.learning_capabilities.errors import LearningCapabilitiesValidationError
from src.learning_capabilities.facade import LearningCapabilitiesFacade
from src.learning_capabilities.schemas import BuildContextBundleCapabilityInput
from src.user.models import User


async def _ensure_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    existing_user = await session.scalar(select(User.id).where(User.id == user_id))
    if existing_user is not None:
        return

    token = str(user_id).replace("-", "")[:12]
    session.add(
        User(
            id=user_id,
            username=f"focus-user-{token}",
            email=f"focus-{token}@example.com",
            password_hash="not-used-in-tests",  # noqa: S106
        )
    )
    await session.flush()


def _embedding(first: float, second: float, third: float) -> list[float]:
    values = [0.0] * 1024
    values[0] = first
    values[1] = second
    values[2] = third
    return values


def _assert_routing_packet_excludes_lesson_and_source_evidence(
    *,
    bundle: object,
    lesson_id: uuid.UUID,
) -> None:
    routing_packet = _build_learning_routing_packet(bundle)
    routing_text = str(routing_packet)
    assert routing_packet["routingPolicy"]["answerEvidenceInjected"] is False
    assert routing_packet["hasSourceFocus"] is True
    assert routing_packet["lessonFocus"] == {
        "lessonId": str(lesson_id),
        "title": "Silk Road Trade Routes",
        "description": "How caravan networks exchanged goods and ideas.",
        "hasLessonContent": True,
        "hasWindowPreview": True,
    }
    assert routing_packet["sourceFocus"]["items"] == [
        {
            "title": "Silk Road Chapter",
            "sourceType": "course_document",
            "documentId": 901,
            "chunkIndex": 0,
            "totalChunks": 2,
            "relevanceScore": 0.82,
            "hasExcerpt": True,
        }
    ]
    assert "Compact first window" not in routing_text
    assert "oasis cities" not in routing_text
    assert "The chapter explains caravan routes" not in routing_text


def test_assistant_learning_tools_are_registered() -> None:
    user_id = uuid.uuid4()
    thread_id = uuid.uuid4()
    tools = [
        *build_learning_query_tools(user_id=user_id),
        *build_learning_action_tools(user_id=user_id, thread_id=thread_id),
    ]
    schemas = {tool.schema["function"]["name"]: tool.schema["function"] for tool in tools}

    assert "search_course_sources" in schemas
    assert "get_lesson_windows" in schemas
    assert "get_concept_tutor_context" in schemas
    assert "generate_concept_probe" in schemas
    learning_tool_names = vars(ai_client)["_LEARNING_TOOL_NAMES"]
    assert "search_course_sources" in learning_tool_names
    assert "get_lesson_windows" in learning_tool_names
    assert "get_concept_tutor_context" in learning_tool_names
    assert "generate_concept_probe" in learning_tool_names
    assert schemas["search_course_sources"]["parameters"]["required"] == ["course_id", "query"]
    assert schemas["get_lesson_windows"]["parameters"]["required"] == ["course_id", "lesson_id"]
    assert schemas["get_concept_tutor_context"]["parameters"]["required"] == ["course_id", "concept_id"]
    assert schemas["generate_concept_probe"]["parameters"]["required"] == ["course_id", "concept_id"]
    assert "Ask a follow-up if course_id is missing" in schemas["search_concepts"]["description"]
    assert "Retrieve uploaded source excerpts" in schemas["search_course_sources"]["description"]
    assert "Not lesson content" in schemas["get_course_outline_state"]["description"]
    assert "what a lesson teaches" in schemas["get_lesson_windows"]["description"]


def test_learning_environment_facts_explain_current_tool_affordances() -> None:
    facts = _build_learning_environment_facts(
        {
            "courseMode": "adaptive",
            "hasActiveProbe": True,
            "hasSourceFocus": True,
            "lessonFocus": {"hasLessonContent": True},
            "conceptFocus": {
                "currentLessonConcept": {"conceptId": str(uuid.uuid4()), "confusorCount": 1},
            },
            "frontierState": {"dueCount": 2},
        }
    )

    assert "Adaptive course: concept state and practice tools may apply." in facts
    assert "Active probe exists: learner answers require server grading." in facts
    assert "Lesson content exists: use lesson windows for lesson-specific answers." in facts
    assert "Current concept is known." in facts
    assert "Learner state has diagnostic signals." in facts
    assert "Source matches exist: retrieve excerpts before source-specific answers." in facts
    assert "Due reviews: 2." in facts


def test_learning_environment_facts_flag_weak_concept_matches() -> None:
    facts = _build_learning_environment_facts(
        {
            "courseMode": "adaptive",
            "hasActiveProbe": False,
            "conceptFocus": {"weakSemanticMatch": True},
        }
    )

    assert "Concept match is weak: search before assuming the target concept." in facts


@pytest.mark.asyncio
async def test_adaptive_context_bundle_includes_concept_focus_and_raw_profile(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid.uuid4()
    course_id = uuid.uuid4()
    current_concept_id = uuid.uuid4()
    confusor_id = uuid.uuid4()
    prereq_id = uuid.uuid4()
    lesson_id = uuid.uuid4()

    await _ensure_user(db_session, user_id)
    db_session.add(
        Course(
            id=course_id,
            user_id=user_id,
            title="Adaptive Algebra",
            description="Learn algebra concept by concept.",
            adaptive_enabled=True,
        )
    )
    db_session.add_all(
        [
            Concept(
                id=current_concept_id,
                domain="math",
                slug=f"linear-equations-{course_id}",
                name="Linear Equations",
                description="Solve one-variable linear equations with inverse operations.",
                embedding=_embedding(0.9, 0.1, 0.0),
            ),
            Concept(
                id=confusor_id,
                domain="math",
                slug=f"linear-inequalities-{course_id}",
                name="Linear Inequalities",
                description="Solve and graph one-variable inequalities.",
                embedding=_embedding(0.86, 0.14, 0.0),
            ),
            Concept(
                id=prereq_id,
                domain="math",
                slug=f"inverse-operations-{course_id}",
                name="Inverse Operations",
                description="Undo operations to isolate a variable.",
                embedding=_embedding(0.4, 0.5, 0.1),
            ),
        ]
    )
    db_session.add_all(
        [
            CourseConcept(course_id=course_id, concept_id=current_concept_id, order_hint=1),
            CourseConcept(course_id=course_id, concept_id=confusor_id, order_hint=2),
            CourseConcept(course_id=course_id, concept_id=prereq_id, order_hint=0),
            ConceptSimilarity(concept_a_id=current_concept_id, concept_b_id=confusor_id, similarity=0.91),
            ConceptPrerequisite(concept_id=current_concept_id, prereq_id=prereq_id),
        ]
    )
    db_session.add(
        Lesson(
            id=lesson_id,
            course_id=course_id,
            concept_id=current_concept_id,
            title="Solving Linear Equations",
            description="Use inverse operations to isolate variables.",
            content="FULL LESSON BODY SHOULD NOT BE AUTO-INJECTED",
            order=1,
        )
    )
    db_session.add_all(
        [
            UserConceptState(
                user_id=user_id,
                concept_id=current_concept_id,
                s_mastery=0.42,
                exposures=3,
                next_review_at=datetime.now(UTC) - timedelta(minutes=5),
                learner_profile={
                    "success_rate": 0.33,
                    "learning_speed": 0.72,
                    "retention_rate": 0.44,
                    "semantic_sensitivity": 0.81,
                },
            ),
            UserConceptState(
                user_id=user_id,
                concept_id=prereq_id,
                s_mastery=0.2,
                exposures=1,
            ),
        ]
    )
    await db_session.commit()

    async def fake_generate_embedding(_self: object, _text: str) -> list[float]:  # noqa: RUF029
        return _embedding(0.9, 0.1, 0.0)

    monkeypatch.setattr("src.learning_capabilities.services.query_service.VectorRAG.generate_embedding", fake_generate_embedding)

    bundle = await LearningCapabilitiesFacade(db_session).build_context_bundle(
        user_id=user_id,
        payload=BuildContextBundleCapabilityInput(
            context_type="course",
            context_id=course_id,
            context_meta={"lesson_id": str(lesson_id)},
            latest_user_text="Why am I stuck solving linear equations?",
        ),
    )
    payload = bundle.model_dump(by_alias=True, mode="json")

    assert payload["courseMode"] == "adaptive"
    assert payload["lessonState"] is None
    assert "FULL LESSON BODY SHOULD NOT BE AUTO-INJECTED" not in str(payload)
    assert payload["learnerProfile"] == {
        "successRate": 0.33,
        "retentionRate": 0.44,
        "learningSpeed": 0.72,
        "semanticSensitivity": 0.81,
    }
    current = payload["conceptFocus"]["currentLessonConcept"]
    assert current["conceptId"] == str(current_concept_id)
    assert current["mastery"] == pytest.approx(0.42)
    assert current["exposures"] == 3
    assert current["due"] is True
    assert current["confusors"][0]["conceptId"] == str(confusor_id)
    assert current["prerequisiteGaps"][0]["conceptId"] == str(prereq_id)
    candidate = payload["conceptFocus"]["semanticCandidates"][0]
    assert candidate["conceptId"] == str(current_concept_id)
    assert candidate["matchSource"] == "embedding"
    assert candidate["matchScore"] > 0.0
    assert candidate["similarity"] > 0.0
    assert payload["activeProbeSuggestion"] == {
        "courseId": str(course_id),
        "conceptId": str(current_concept_id),
        "lessonId": str(lesson_id),
        "learnerAskedCheck": False,
        "learnerExpressedUncertainty": True,
        "learnerSharedReasoning": False,
        "repeatedRecentMisses": False,
    }

    search_without_state = await LearningCapabilitiesFacade(db_session).execute_read_capability(
        user_id=user_id,
        capability_name="search_concepts",
        payload={"course_id": str(course_id), "query": "linear equations", "include_state": False},
    )
    stateless_match = search_without_state["items"][0]
    assert stateless_match["mastery"] is None
    assert stateless_match["exposures"] == 0
    assert stateless_match["prerequisiteGaps"] == []


@pytest.mark.asyncio
async def test_get_concept_tutor_context_returns_deterministic_adaptive_evidence(db_session: AsyncSession) -> None:
    user_id = uuid.uuid4()
    course_id = uuid.uuid4()
    concept_id = uuid.uuid4()
    prereq_id = uuid.uuid4()
    confusor_id = uuid.uuid4()
    downstream_id = uuid.uuid4()
    lesson_id = uuid.uuid4()
    version_id = uuid.uuid4()
    now = datetime.now(UTC)

    await _ensure_user(db_session, user_id)
    db_session.add(Course(id=course_id, user_id=user_id, title="Tutor Algebra", description="Adaptive tutor test.", adaptive_enabled=True))
    db_session.add_all(
        [
            Concept(id=concept_id, domain="math", slug=f"target-{concept_id}", name="Linear Equations", description="Solve for x.", difficulty=2),
            Concept(id=prereq_id, domain="math", slug=f"prereq-{prereq_id}", name="Inverse Operations", description="Undo operations."),
            Concept(id=confusor_id, domain="math", slug=f"confusor-{confusor_id}", name="Linear Inequalities", description="Compare expressions."),
            Concept(id=downstream_id, domain="math", slug=f"downstream-{downstream_id}", name="Systems", description="Solve pairs."),
            CourseConcept(course_id=course_id, concept_id=concept_id, order_hint=1),
            CourseConcept(course_id=course_id, concept_id=prereq_id, order_hint=0),
            CourseConcept(course_id=course_id, concept_id=confusor_id, order_hint=2),
            CourseConcept(course_id=course_id, concept_id=downstream_id, order_hint=3),
            ConceptPrerequisite(concept_id=concept_id, prereq_id=prereq_id),
            ConceptPrerequisite(concept_id=downstream_id, prereq_id=concept_id),
            ConceptSimilarity(concept_a_id=concept_id, concept_b_id=confusor_id, similarity=0.88),
            UserConceptState(
                user_id=user_id,
                concept_id=concept_id,
                s_mastery=0.31,
                exposures=4,
                next_review_at=now - timedelta(hours=1),
                last_seen_at=now,
                learner_profile={
                    "success_rate": 0.2,
                    "retention_rate": 0.4,
                    "learning_speed": 0.7,
                    "semantic_sensitivity": 0.9,
                },
            ),
            UserConceptState(user_id=user_id, concept_id=prereq_id, s_mastery=0.1, exposures=1),
        ]
    )
    lesson = Lesson(
        id=lesson_id,
        course_id=course_id,
        concept_id=concept_id,
        title="Solving Linear Equations",
        description="Target lesson.",
        content="Tutor context should not need this full body.",
        order=1,
    )
    db_session.add(lesson)
    await db_session.flush()
    db_session.add(
        LessonVersion(
            id=version_id,
            lesson_id=lesson_id,
            major_version=1,
            minor_version=0,
            version_kind="first_pass",
            content="Version body",
            generation_metadata={},
        )
    )
    await db_session.flush()
    lesson.current_version_id = version_id
    db_session.add(
        LessonVersionWindow(
            lesson_version_id=version_id,
            window_index=0,
            title="Equation Steps",
            content="Step 1: isolate the variable.",
            estimated_minutes=4,
        )
    )
    db_session.add_all(
        [
            ProbeEvent(id=uuid.uuid4(), user_id=user_id, concept_id=concept_id, ts=now - timedelta(minutes=2), correct=False, rating=1),
            ProbeEvent(id=uuid.uuid4(), user_id=user_id, concept_id=concept_id, ts=now - timedelta(minutes=4), correct=True, rating=4),
        ]
    )
    await db_session.commit()

    tutor_context = await LearningCapabilitiesFacade(db_session).execute_read_capability(
        user_id=user_id,
        capability_name="get_concept_tutor_context",
        payload={"course_id": str(course_id), "concept_id": str(concept_id)},
    )

    assert tutor_context["courseMode"] == "adaptive"
    assert tutor_context["conceptName"] == "Linear Equations"
    assert tutor_context["difficulty"] == pytest.approx(2.0)
    assert tutor_context["lessonId"] == str(lesson_id)
    assert tutor_context["mastery"] == pytest.approx(0.31)
    assert tutor_context["exposures"] == 4
    assert tutor_context["due"] is True
    assert tutor_context["learnerProfile"]["successRate"] == pytest.approx(0.2)
    assert tutor_context["recentProbes"][0]["correct"] is False
    assert tutor_context["evidence"]["recentProbeCount"] == 2
    assert tutor_context["evidence"]["recentCorrectCount"] == 1
    assert tutor_context["evidence"]["masteryEvidenceCount"] == 6
    assert tutor_context["evidence"]["hasSparseEvidence"] is False
    assert tutor_context["prerequisiteGaps"][0]["conceptId"] == str(prereq_id)
    assert tutor_context["semanticConfusors"][0]["conceptId"] == str(confusor_id)
    assert tutor_context["downstreamBlocked"][0]["conceptId"] == str(downstream_id)
    assert tutor_context["hasVerifiedContent"] is True
    assert tutor_context["contentSourceCount"] == 1
    assert [cause["kind"] for cause in tutor_context["candidateCauses"]] == [
        "current_concept",
        "recent_miss",
        "prerequisite_gap",
        "semantic_confusor",
    ]
    assert tutor_context["deterministicSignals"]["hasPrerequisiteGap"] is True
    assert tutor_context["deterministicSignals"]["hasRecentMiss"] is True
    assert tutor_context["deterministicSignals"]["hasSemanticConfusor"] is True
    assert "probe" in tutor_context["allowedTutorMoves"]

    limited_context = await LearningCapabilitiesFacade(db_session).execute_read_capability(
        user_id=user_id,
        capability_name="get_concept_tutor_context",
        payload={
            "course_id": str(course_id),
            "concept_id": str(concept_id),
            "include_recent_probes": False,
            "include_lesson_summary": False,
        },
    )
    assert limited_context["recentProbes"] == []
    assert "recent_miss" not in [cause["kind"] for cause in limited_context["candidateCauses"]]
    assert limited_context["hasVerifiedContent"] is False
    assert limited_context["contentSourceCount"] == 0


@pytest.mark.asyncio
async def test_get_concept_tutor_context_returns_not_applicable_reasons(db_session: AsyncSession) -> None:
    user_id = uuid.uuid4()
    attacker_id = uuid.uuid4()
    standard_course_id = uuid.uuid4()
    adaptive_course_id = uuid.uuid4()
    concept_id = uuid.uuid4()

    await _ensure_user(db_session, user_id)
    await _ensure_user(db_session, attacker_id)
    db_session.add_all(
        [
            Course(id=standard_course_id, user_id=user_id, title="Standard", description="No graph.", adaptive_enabled=False),
            Course(id=adaptive_course_id, user_id=user_id, title="Adaptive", description="Has graph.", adaptive_enabled=True),
            Concept(id=concept_id, domain="math", slug=f"unassigned-{concept_id}", name="Unassigned", description="Not linked."),
        ]
    )
    await db_session.commit()

    facade = LearningCapabilitiesFacade(db_session)
    standard_result = await facade.execute_read_capability(
        user_id=user_id,
        capability_name="get_concept_tutor_context",
        payload={"course_id": str(standard_course_id), "concept_id": str(concept_id)},
    )
    unassigned_result = await facade.execute_read_capability(
        user_id=user_id,
        capability_name="get_concept_tutor_context",
        payload={"course_id": str(adaptive_course_id), "concept_id": str(concept_id)},
    )

    assert standard_result["courseMode"] == "standard"
    assert standard_result["reason"] == "standard_course_has_no_concept_graph"
    assert unassigned_result["courseMode"] == "adaptive"
    assert unassigned_result["reason"] == "concept_not_assigned_to_course"

    with pytest.raises(NotFoundError):
        await facade.execute_read_capability(
            user_id=attacker_id,
            capability_name="get_concept_tutor_context",
            payload={"course_id": str(adaptive_course_id), "concept_id": str(concept_id)},
        )


@pytest.mark.asyncio
async def test_get_concept_tutor_context_marks_sparse_stale_evidence(db_session: AsyncSession) -> None:
    user_id = uuid.uuid4()
    course_id = uuid.uuid4()
    concept_id = uuid.uuid4()

    await _ensure_user(db_session, user_id)
    db_session.add(Course(id=course_id, user_id=user_id, title="Sparse Tutor", description="Sparse evidence.", adaptive_enabled=True))
    db_session.add_all(
        [
            Concept(id=concept_id, domain="math", slug=f"sparse-{concept_id}", name="Sparse Concept", description="Little evidence."),
            CourseConcept(course_id=course_id, concept_id=concept_id, order_hint=1),
            UserConceptState(
                user_id=user_id,
                concept_id=concept_id,
                s_mastery=0.0,
                exposures=0,
                last_seen_at=datetime.now(UTC) - timedelta(days=45),
            ),
        ]
    )
    await db_session.commit()

    tutor_context = await LearningCapabilitiesFacade(db_session).execute_read_capability(
        user_id=user_id,
        capability_name="get_concept_tutor_context",
        payload={"course_id": str(course_id), "concept_id": str(concept_id)},
    )

    assert tutor_context["evidence"]["masteryEvidenceCount"] == 0
    assert tutor_context["evidence"]["hasSparseEvidence"] is True
    assert tutor_context["evidence"]["hasStaleEvidence"] is True


@pytest.mark.asyncio
async def test_standard_context_bundle_uses_lesson_focus_and_search_concepts_reason(
    db_session: AsyncSession,
) -> None:
    user_id = uuid.uuid4()
    course_id = uuid.uuid4()
    lesson_id = uuid.uuid4()
    version_id = uuid.uuid4()

    await _ensure_user(db_session, user_id)
    db_session.add(
        Course(
            id=course_id,
            user_id=user_id,
            title="Standard History",
            description="A normal lesson-based course.",
            adaptive_enabled=False,
        )
    )
    lesson = Lesson(
        id=lesson_id,
        course_id=course_id,
        title="The Silk Road",
        description="Trade networks across Eurasia.",
        content="STANDARD FULL LESSON BODY SHOULD NOT BE AUTO-INJECTED",
        order=1,
    )
    db_session.add(lesson)
    await db_session.flush()
    db_session.add(
        LessonVersion(
            id=version_id,
            lesson_id=lesson_id,
            major_version=1,
            minor_version=0,
            version_kind="first_pass",
            content="Version body",
            generation_metadata={},
        )
    )
    await db_session.flush()
    lesson.current_version_id = version_id
    await db_session.flush()
    db_session.add(
        LessonVersionWindow(
            lesson_version_id=version_id,
            window_index=0,
            title="Trade Routes",
            content="Compact preview about caravan routes and exchange.",
            estimated_minutes=6,
        )
    )
    await db_session.commit()

    facade = LearningCapabilitiesFacade(db_session)
    bundle = await facade.build_context_bundle(
        user_id=user_id,
        payload=BuildContextBundleCapabilityInput(
            context_type="course",
            context_id=course_id,
            context_meta={"lesson_id": str(lesson_id)},
            latest_user_text="Explain this part another way.",
        ),
    )
    payload = bundle.model_dump(by_alias=True, mode="json")

    assert payload["courseMode"] == "standard"
    assert payload["conceptFocus"] is None
    assert payload["learnerProfile"] is None
    assert payload["frontierState"] is None
    assert payload["lessonState"] is None
    assert payload["lessonFocus"]["lessonId"] == str(lesson_id)
    assert payload["lessonFocus"]["windowPreview"] == "Compact preview about caravan routes and exchange."
    assert "STANDARD FULL LESSON BODY SHOULD NOT BE AUTO-INJECTED" not in str(payload)

    search_result = await facade.execute_read_capability(
        user_id=user_id,
        capability_name="search_concepts",
        payload={"course_id": str(course_id), "query": "trade routes"},
    )
    assert search_result == {
        "courseId": str(course_id),
        "courseMode": "standard",
        "items": [],
        "reason": "standard_course_has_no_concept_graph",
    }


@pytest.mark.asyncio
async def test_course_grounding_tools_return_source_excerpts_and_lesson_windows(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid.uuid4()
    course_id = uuid.uuid4()
    lesson_id = uuid.uuid4()
    version_id = uuid.uuid4()

    await _ensure_user(db_session, user_id)
    db_session.add(
        Course(
            id=course_id,
            user_id=user_id,
            title="Standard Trade Course",
            description="Grounded source and lesson-window course.",
            adaptive_enabled=False,
        )
    )
    lesson = Lesson(
        id=lesson_id,
        course_id=course_id,
        title="Silk Road Trade Routes",
        description="How caravan networks exchanged goods and ideas.",
        content="FULL SOURCE LESSON BODY SHOULD NOT BE AUTO-INJECTED",
        order=1,
    )
    db_session.add(lesson)
    db_session.add(
        CourseDocument(
            id=901,
            course_id=course_id,
            document_type="pdf",
            title="Silk Road Chapter",
            status="embedded",
            embedded_at=datetime.now(UTC),
        )
    )
    await db_session.flush()
    db_session.add(
        LessonVersion(
            id=version_id,
            lesson_id=lesson_id,
            major_version=1,
            minor_version=0,
            version_kind="first_pass",
            content="Version body with two windows",
            generation_metadata={},
        )
    )
    await db_session.flush()
    lesson.current_version_id = version_id
    db_session.add_all(
        [
            LessonVersionWindow(
                lesson_version_id=version_id,
                window_index=0,
                title="Route Overview",
                content="Compact first window about caravan routes and exchange.",
                estimated_minutes=5,
            ),
            LessonVersionWindow(
                lesson_version_id=version_id,
                window_index=1,
                title="Method Order",
                content="Step 1: locate the oasis cities. Step 2: trace goods and cultural exchange.",
                estimated_minutes=6,
            ),
        ]
    )
    await db_session.commit()

    async def fake_search_documents(  # noqa: RUF029
        _self: object,
        _session: AsyncSession,
        received_user_id: uuid.UUID,
        received_course_id: uuid.UUID,
        query: str,
        top_k: int | None = None,
    ) -> list[SearchResult]:
        assert received_user_id == user_id
        assert received_course_id == course_id
        assert "uploaded chapter" in query
        assert top_k in {2, 5}
        long_excerpt = " ".join(["The chapter explains caravan routes through oasis cities using silk, spices, and ideas."] * 20)
        return [
            SearchResult(
                chunk_id="source-chunk-0",
                content=long_excerpt,
                similarity_score=0.82,
                metadata={"title": "Silk Road Chapter", "document_id": 901, "chunk_index": 0, "total_chunks": 2},
            )
        ]

    monkeypatch.setattr("src.learning_capabilities.services.query_service.RAGService.search_documents", fake_search_documents)

    facade = LearningCapabilitiesFacade(db_session)
    bundle = await facade.build_context_bundle(
        user_id=user_id,
        payload=BuildContextBundleCapabilityInput(
            context_type="course",
            context_id=course_id,
            context_meta={"lesson_id": str(lesson_id)},
            latest_user_text="What does the uploaded chapter say about caravan trade routes?",
        ),
    )
    payload = bundle.model_dump(by_alias=True, mode="json")

    assert payload["courseMode"] == "standard"
    assert payload["sourceFocus"]["items"][0]["title"] == "Silk Road Chapter"
    assert payload["sourceFocus"]["items"][0]["sourceType"] == "course_document"
    assert payload["sourceFocus"]["items"][0]["similarity"] == pytest.approx(0.82)
    assert len(payload["sourceFocus"]["items"][0]["excerpt"]) <= 900
    assert payload["sourceFocus"]["items"][0]["excerpt"].endswith("...")
    assert payload["lessonFocus"]["windowPreview"] == "Compact first window about caravan routes and exchange."
    assert "FULL SOURCE LESSON BODY SHOULD NOT BE AUTO-INJECTED" not in str(payload)

    _assert_routing_packet_excludes_lesson_and_source_evidence(bundle=bundle, lesson_id=lesson_id)

    whitespace_search = await facade.execute_read_capability(
        user_id=user_id,
        capability_name="search_course_sources",
        payload={"course_id": str(course_id), "query": "   "},
    )
    assert whitespace_search["items"] == []

    source_search = await facade.execute_read_capability(
        user_id=user_id,
        capability_name="search_course_sources",
        payload={"course_id": str(course_id), "query": "uploaded chapter caravan routes"},
    )
    assert source_search["items"][0]["documentId"] == 901
    assert "oasis cities" in source_search["items"][0]["excerpt"]

    windows = await facade.execute_read_capability(
        user_id=user_id,
        capability_name="get_lesson_windows",
        payload={"course_id": str(course_id), "lesson_id": str(lesson_id), "window_index": 1, "limit": 1},
    )
    assert windows["courseId"] == str(course_id)
    assert windows["lessonId"] == str(lesson_id)
    assert windows["versionId"] == str(version_id)
    assert len(windows["items"]) == 1
    assert windows["items"][0]["windowIndex"] == 1
    assert "Step 1" in windows["items"][0]["content"]


@pytest.mark.asyncio
async def test_get_lesson_windows_ignores_stale_current_version_links(db_session: AsyncSession) -> None:
    user_id = uuid.uuid4()
    course_id = uuid.uuid4()
    lesson_id = uuid.uuid4()
    other_lesson_id = uuid.uuid4()
    version_id = uuid.uuid4()

    await _ensure_user(db_session, user_id)
    db_session.add(
        Course(
            id=course_id,
            user_id=user_id,
            title="Window Safety",
            description="Course for stale version safety.",
            adaptive_enabled=False,
        )
    )
    db_session.add_all(
        [
            Lesson(
                id=lesson_id,
                course_id=course_id,
                title="Target",
                description="Target lesson.",
                content="Target content.",
                order=1,
            ),
            Lesson(
                id=other_lesson_id,
                course_id=course_id,
                title="Other",
                description="Other lesson.",
                content="Other content.",
                order=2,
            ),
        ]
    )
    await db_session.flush()
    db_session.add(
        LessonVersion(
            id=version_id,
            lesson_id=other_lesson_id,
            major_version=1,
            minor_version=0,
            version_kind="first_pass",
            content="Other content",
            generation_metadata={},
        )
    )
    await db_session.flush()
    target_lesson = await db_session.get(Lesson, lesson_id)
    assert target_lesson is not None
    target_lesson.current_version_id = version_id
    db_session.add(
        LessonVersionWindow(
            lesson_version_id=version_id,
            window_index=0,
            title="Other Window",
            content="This window belongs to another lesson.",
            estimated_minutes=2,
        )
    )
    await db_session.commit()

    facade = LearningCapabilitiesFacade(db_session)
    windows = await facade.execute_read_capability(
        user_id=user_id,
        capability_name="get_lesson_windows",
        payload={"course_id": str(course_id), "lesson_id": str(lesson_id)},
    )

    assert windows["items"] == []
    assert windows["versionId"] is None


@pytest.mark.asyncio
async def test_course_grounding_tools_do_not_cross_course_ownership(db_session: AsyncSession) -> None:
    owner_id = uuid.uuid4()
    attacker_id = uuid.uuid4()
    course_id = uuid.uuid4()
    lesson_id = uuid.uuid4()

    await _ensure_user(db_session, owner_id)
    await _ensure_user(db_session, attacker_id)
    db_session.add(
        Course(
            id=course_id,
            user_id=owner_id,
            title="Private Source Course",
            description="Should remain private.",
            adaptive_enabled=False,
        )
    )
    db_session.add(
        Lesson(
            id=lesson_id,
            course_id=course_id,
            title="Private Lesson",
            description="Private windowed lesson.",
            content="Private content",
            order=1,
        )
    )
    await db_session.commit()

    facade = LearningCapabilitiesFacade(db_session)
    with pytest.raises(NotFoundError):
        await facade.execute_read_capability(
            user_id=attacker_id,
            capability_name="search_course_sources",
            payload={"course_id": str(course_id), "query": "private source"},
        )
    with pytest.raises(NotFoundError):
        await facade.execute_read_capability(
            user_id=attacker_id,
            capability_name="get_lesson_windows",
            payload={"course_id": str(course_id), "lesson_id": str(lesson_id)},
        )


@pytest.mark.asyncio
async def test_search_concepts_returns_empty_for_unrelated_adaptive_query(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid.uuid4()
    course_id = uuid.uuid4()
    concept_id = uuid.uuid4()

    await _ensure_user(db_session, user_id)
    db_session.add(
        Course(
            id=course_id,
            user_id=user_id,
            title="Adaptive Algebra",
            description="Learn algebra concept by concept.",
            adaptive_enabled=True,
        )
    )
    db_session.add(
        Concept(
            id=concept_id,
            domain="math",
            slug=f"linear-equations-empty-{course_id}",
            name="Linear Equations",
            description="Solve one-variable linear equations with inverse operations.",
            embedding=_embedding(1.0, 0.0, 0.0),
        )
    )
    db_session.add(CourseConcept(course_id=course_id, concept_id=concept_id, order_hint=1))
    await db_session.commit()

    async def fake_generate_embedding(_self: object, _text: str) -> list[float]:  # noqa: RUF029
        return _embedding(0.0, 1.0, 0.0)

    monkeypatch.setattr("src.learning_capabilities.services.query_service.VectorRAG.generate_embedding", fake_generate_embedding)

    facade = LearningCapabilitiesFacade(db_session)
    search_result = await facade.execute_read_capability(
        user_id=user_id,
        capability_name="search_concepts",
        payload={"course_id": str(course_id), "query": "ancient maritime trade networks"},
    )

    assert search_result == {"courseId": str(course_id), "courseMode": "adaptive", "items": [], "reason": None}

    bundle = await facade.build_context_bundle(
        user_id=user_id,
        payload=BuildContextBundleCapabilityInput(
            context_type="course",
            context_id=course_id,
            context_meta={},
            latest_user_text="ancient maritime trade networks",
        ),
    )

    assert bundle.concept_focus is None


@pytest.mark.asyncio
async def test_search_concepts_does_not_cross_course_ownership(db_session: AsyncSession) -> None:
    owner_id = uuid.uuid4()
    attacker_id = uuid.uuid4()
    course_id = uuid.uuid4()

    await _ensure_user(db_session, owner_id)
    await _ensure_user(db_session, attacker_id)
    db_session.add(
        Course(
            id=course_id,
            user_id=owner_id,
            title="Private Adaptive Course",
            description="Should remain private.",
            adaptive_enabled=True,
        )
    )
    await db_session.commit()

    with pytest.raises(NotFoundError):
        await LearningCapabilitiesFacade(db_session).execute_read_capability(
            user_id=attacker_id,
            capability_name="search_concepts",
            payload={"course_id": str(course_id), "query": "private concept"},
        )


@pytest.mark.asyncio
async def test_generate_concept_probe_returns_visible_probe_and_stores_hidden_metadata(  # noqa: PLR0915
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid.uuid4()
    course_id = uuid.uuid4()
    concept_id = uuid.uuid4()
    second_concept_id = uuid.uuid4()
    lesson_id = uuid.uuid4()
    other_lesson_id = uuid.uuid4()
    thread_id = uuid.uuid4()

    await _ensure_user(db_session, user_id)
    db_session.add(
        Course(
            id=course_id,
            user_id=user_id,
            title="Adaptive Probe Course",
            description="Generate chat probes.",
            adaptive_enabled=True,
        )
    )
    db_session.add(
        Concept(
            id=concept_id,
            domain="math",
            slug=f"probe-linear-equations-{course_id}",
            name="Linear Equations",
            description="Solve equations by inverse operations.",
        )
    )
    db_session.add(
        Concept(
            id=second_concept_id,
            domain="math",
            slug=f"probe-graph-lines-{course_id}",
            name="Graph Lines",
            description="Graph equations on a coordinate plane.",
        )
    )
    db_session.add(CourseConcept(course_id=course_id, concept_id=concept_id, order_hint=1))
    db_session.add(CourseConcept(course_id=course_id, concept_id=second_concept_id, order_hint=2))
    db_session.add(
        Lesson(
            id=lesson_id,
            course_id=course_id,
            concept_id=concept_id,
            title="Solve Equations",
            description="Practice solving equations.",
            content="Practice body",
            order=1,
        )
    )
    db_session.add(
        AssistantConversation(
            id=thread_id,
            user_id=user_id,
            context_type="course",
            context_id=course_id,
            context_meta={"lesson_id": str(lesson_id)},
        )
    )
    await db_session.commit()

    generated_concept_ids: list[uuid.UUID] = []

    async def fake_generate_drills(  # noqa: RUF029
        _self: object,
        *,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        concept_id: uuid.UUID,
        count: int,
        learner_context: str | None = None,
    ) -> list[PracticeDrillItem]:
        assert user_id
        assert course_id
        assert concept_id
        assert count == 1
        assert learner_context == "The learner is adding four to both ratio quantities."
        generated_concept_ids.append(concept_id)
        return [
            PracticeDrillItem(
                concept_id=concept_id,
                lesson_id=lesson_id,
                question="Solve 2x + 3 = 11.",
                expected_answer="x = 4",
                answer_kind="latex",
                hints=["Undo addition first."],
                structure_signature="solve.linear.n",
                predicted_p_correct=0.61,
                target_probability=0.62,
                target_low=0.52,
                target_high=0.72,
                core_model="test-model",
            )
        ]

    monkeypatch.setattr(
        "src.learning_capabilities.services.action_service.PracticeDrillService.generate_drills",
        fake_generate_drills,
    )

    result = await LearningCapabilitiesFacade(db_session).execute_action_capability(
        user_id=user_id,
        capability_name="generate_concept_probe",
        payload={
            "course_id": str(course_id),
            "concept_id": str(concept_id),
            "count": 1,
            "practice_context": "chat",
            "learner_context": "The learner is adding four to both ratio quantities.",
            "thread_id": str(thread_id),
            "lesson_id": str(lesson_id),
        },
    )
    await db_session.commit()

    assert result["courseMode"] == "adaptive"
    assert result["activeProbeId"]
    assert result["probe"] == {
        "activeProbeId": result["activeProbeId"],
        "question": "Solve 2x + 3 = 11.",
        "answerKind": "latex",
        "probeFamily": "free_recall",
        "rendererKind": "free_form",
        "choices": [],
        "hints": ["Undo addition first."],
        "courseId": str(course_id),
        "conceptId": str(concept_id),
        "lessonId": str(lesson_id),
    }
    assert "expectedAnswer" not in result["probe"]
    assert "predictedPCorrect" not in result["probe"]
    assert generated_concept_ids == [concept_id]

    stored_probe = await db_session.scalar(
        select(AssistantActiveProbe).where(AssistantActiveProbe.id == uuid.UUID(result["activeProbeId"]))
    )
    assert stored_probe is not None
    assert stored_probe.user_id == user_id
    assert stored_probe.conversation_id == thread_id
    assert stored_probe.expected_answer == "x = 4"
    assert stored_probe.structure_signature == "solve.linear.n"
    assert stored_probe.predicted_p_correct == pytest.approx(0.61)

    repeated = await LearningCapabilitiesFacade(db_session).execute_action_capability(
        user_id=user_id,
        capability_name="generate_concept_probe",
        payload={
            "course_id": str(course_id),
            "concept_id": str(concept_id),
            "thread_id": str(thread_id),
            "lesson_id": str(lesson_id),
        },
    )
    same_lesson = await LearningCapabilitiesFacade(db_session).execute_action_capability(
        user_id=user_id,
        capability_name="generate_concept_probe",
        payload={
            "course_id": str(course_id),
            "concept_id": str(second_concept_id),
            "thread_id": str(thread_id),
            "lesson_id": str(lesson_id),
        },
    )
    wrong_existing_lesson = await LearningCapabilitiesFacade(db_session).execute_action_capability(
        user_id=user_id,
        capability_name="generate_concept_probe",
        payload={
            "course_id": str(course_id),
            "concept_id": str(concept_id),
            "thread_id": str(thread_id),
            "lesson_id": str(other_lesson_id),
        },
    )
    wrong_lesson = await LearningCapabilitiesFacade(db_session).execute_action_capability(
        user_id=user_id,
        capability_name="generate_concept_probe",
        payload={
            "course_id": str(course_id),
            "concept_id": str(second_concept_id),
            "thread_id": str(thread_id),
            "lesson_id": str(other_lesson_id),
        },
    )
    active_probe_count = await db_session.scalar(
        select(func.count(AssistantActiveProbe.id)).where(
            AssistantActiveProbe.user_id == user_id,
            AssistantActiveProbe.conversation_id == thread_id,
            AssistantActiveProbe.course_id == course_id,
            AssistantActiveProbe.concept_id == concept_id,
            AssistantActiveProbe.status == "active",
        )
    )
    assert repeated["activeProbeId"] == result["activeProbeId"]
    assert same_lesson["reason"] == "concept_not_assigned_to_current_lesson"
    assert wrong_existing_lesson["reason"] == "concept_not_assigned_to_current_lesson"
    assert wrong_lesson["reason"] == "concept_not_assigned_to_current_lesson"
    assert active_probe_count == 1
    assert generated_concept_ids == [concept_id]


@pytest.mark.asyncio
async def test_generate_concept_probe_requires_thread_to_match_course(db_session: AsyncSession) -> None:
    user_id = uuid.uuid4()
    course_id = uuid.uuid4()
    other_course_id = uuid.uuid4()
    concept_id = uuid.uuid4()
    thread_id = uuid.uuid4()

    await _ensure_user(db_session, user_id)
    db_session.add_all(
        [
            Course(
                id=course_id,
                user_id=user_id,
                title="Adaptive Probe Course",
                description="Generate chat probes.",
                adaptive_enabled=True,
            ),
            Course(
                id=other_course_id,
                user_id=user_id,
                title="Other Course",
                description="Different thread course.",
                adaptive_enabled=True,
            ),
        ]
    )
    db_session.add(
        AssistantConversation(
            id=thread_id,
            user_id=user_id,
            context_type="course",
            context_id=other_course_id,
            context_meta={},
        )
    )
    await db_session.commit()

    with pytest.raises(LearningCapabilitiesValidationError, match="Assistant thread not found or access denied"):
        await LearningCapabilitiesFacade(db_session).execute_action_capability(
            user_id=user_id,
            capability_name="generate_concept_probe",
            payload={
                "course_id": str(course_id),
                "concept_id": str(concept_id),
                "thread_id": str(thread_id),
            },
        )


@pytest.mark.asyncio
async def test_generate_concept_probe_standard_course_is_not_applicable(db_session: AsyncSession) -> None:
    user_id = uuid.uuid4()
    course_id = uuid.uuid4()
    concept_id = uuid.uuid4()

    await _ensure_user(db_session, user_id)
    db_session.add(
        Course(
            id=course_id,
            user_id=user_id,
            title="Standard Probe Course",
            description="No adaptive concept graph.",
            adaptive_enabled=False,
        )
    )
    await db_session.commit()

    result = await LearningCapabilitiesFacade(db_session).execute_action_capability(
        user_id=user_id,
        capability_name="generate_concept_probe",
        payload={"course_id": str(course_id), "concept_id": str(concept_id)},
    )
    submit_result = await LearningCapabilitiesFacade(db_session).execute_action_capability(
        user_id=user_id,
        capability_name="submit_concept_probe_result",
        payload={"course_id": str(course_id), "active_probe_id": str(uuid.uuid4()), "learner_answer": "4"},
    )

    assert result == {
        "courseId": str(course_id),
        "courseMode": "standard",
        "conceptId": str(concept_id),
        "activeProbeId": None,
        "probe": None,
        "reason": "standard_course_has_no_concept_graph",
    }
    assert submit_result["courseMode"] == "standard"
    assert submit_result["reason"] == "standard_course_has_no_concept_graph"


@pytest.mark.asyncio
async def test_generate_concept_probe_returns_stable_unavailable_on_generation_failure(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = uuid.uuid4()
    course_id = uuid.uuid4()
    concept_id = uuid.uuid4()
    lesson_id = uuid.uuid4()
    thread_id = uuid.uuid4()

    await _ensure_user(db_session, user_id)
    db_session.add_all(
        [
            Course(
                id=course_id,
                user_id=user_id,
                title="Adaptive Failure Course",
                description="Generation can fail.",
                adaptive_enabled=True,
            ),
            Concept(
                id=concept_id,
                domain="math",
                slug=f"probe-failure-{concept_id}",
                name="Linear Equations",
                description="Solve equations.",
            ),
            CourseConcept(course_id=course_id, concept_id=concept_id, order_hint=1),
            Lesson(
                id=lesson_id,
                course_id=course_id,
                concept_id=concept_id,
                title="Solve Equations",
                description="Practice equations.",
                content="Practice body",
                order=1,
            ),
            AssistantConversation(
                id=thread_id,
                user_id=user_id,
                context_type="course",
                context_id=course_id,
                context_meta={},
            ),
        ]
    )
    await db_session.commit()

    async def fail_generate_drills(self: object, **_kwargs: object) -> list[PracticeDrillItem]:  # noqa: RUF029
        del self
        detail = "practice provider failed"
        raise AIProviderError(detail)

    monkeypatch.setattr(
        "src.learning_capabilities.services.action_service.PracticeDrillService.generate_drills",
        fail_generate_drills,
    )

    result = await LearningCapabilitiesFacade(db_session).execute_action_capability(
        user_id=user_id,
        capability_name="generate_concept_probe",
        payload={"course_id": str(course_id), "concept_id": str(concept_id), "thread_id": str(thread_id)},
    )

    assert result == {
        "courseId": str(course_id),
        "courseMode": "adaptive",
        "conceptId": str(concept_id),
        "activeProbeId": None,
        "probe": None,
        "reason": "probe_generation_unavailable",
    }


@pytest.mark.asyncio
async def test_context_bundle_includes_active_chat_probe_without_hidden_answer(db_session: AsyncSession) -> None:
    user_id = uuid.uuid4()
    course_id = uuid.uuid4()
    concept_id = uuid.uuid4()
    lesson_id = uuid.uuid4()
    thread_id = uuid.uuid4()
    active_probe_id = uuid.uuid4()

    await _ensure_user(db_session, user_id)
    db_session.add_all(
        [
            Course(
                id=course_id,
                user_id=user_id,
                title="Adaptive Active Probe Course",
                description="Active probe context.",
                adaptive_enabled=True,
            ),
            Concept(
                id=concept_id,
                domain="math",
                slug=f"active-chat-probe-{concept_id}",
                name="Linear Equations",
                description="Solve equations.",
            ),
            CourseConcept(course_id=course_id, concept_id=concept_id, order_hint=1),
            Lesson(
                id=lesson_id,
                course_id=course_id,
                concept_id=concept_id,
                title="Solve Equations",
                description="Practice equations.",
                content="Practice body",
                order=1,
            ),
            AssistantConversation(
                id=thread_id,
                user_id=user_id,
                context_type="course",
                context_id=course_id,
                context_meta={},
            ),
        ]
    )
    await db_session.flush()
    db_session.add(
        AssistantActiveProbe(
            id=active_probe_id,
            user_id=user_id,
            conversation_id=thread_id,
            course_id=course_id,
            concept_id=concept_id,
            lesson_id=lesson_id,
            question="Solve 2x + 3 = 11.",
            expected_answer="x = 4",
            answer_kind="latex",
            hints=["Undo addition first."],
            structure_signature="solve.linear.n",
            predicted_p_correct=0.61,
            target_probability=0.62,
            target_low=0.52,
            target_high=0.72,
            core_model="test-model",
        )
    )
    db_session.add(
        LearningQuestion(
            id=active_probe_id,
            user_id=user_id,
            course_id=course_id,
            concept_id=concept_id,
            lesson_id=lesson_id,
            question="Solve 2x + 3 = 11.",
            expected_answer="x = 4",
            answer_kind="latex",
            grade_kind="practice_answer",
            expected_payload={},
            question_payload={
                "answerKind": "latex",
                "probeFamily": "free_recall",
                "rendererKind": "free_form",
                "choices": [],
                "hints": ["Undo addition first."],
            },
            hints=["Undo addition first."],
            structure_signature="solve.linear.n",
            predicted_p_correct=0.61,
            target_probability=0.62,
            target_low=0.52,
            target_high=0.72,
            core_model="test-model",
            practice_context="chat",
        )
    )
    await db_session.commit()

    bundle = await LearningCapabilitiesFacade(db_session).build_context_bundle(
        user_id=user_id,
        payload=BuildContextBundleCapabilityInput(
            context_type="course",
            context_id=course_id,
            context_meta={"lesson_id": str(lesson_id), "thread_id": str(thread_id)},
            latest_user_text="Here is my answer: x = 4",
        ),
    )

    packet = bundle.model_dump(by_alias=True, mode="json")
    assert packet["activeChatProbe"] == {
        "activeProbeId": str(active_probe_id),
        "courseId": str(course_id),
        "conceptId": str(concept_id),
        "lessonId": str(lesson_id),
        "question": "Solve 2x + 3 = 11.",
        "answerKind": "latex",
        "probeFamily": "free_recall",
        "rendererKind": "free_form",
        "choices": [],
        "hints": ["Undo addition first."],
    }
    assert "x = 4" not in str(packet["activeChatProbe"])
    assert "expectedAnswer" not in str(packet)

    other_lesson_bundle = await LearningCapabilitiesFacade(db_session).build_context_bundle(
        user_id=user_id,
        payload=BuildContextBundleCapabilityInput(
            context_type="course",
            context_id=course_id,
            context_meta={"lesson_id": str(uuid.uuid4()), "thread_id": str(thread_id)},
            latest_user_text="Here is my answer: x = 4",
        ),
    )
    assert other_lesson_bundle.active_chat_probe is None

    course_only_bundle = await LearningCapabilitiesFacade(db_session).build_context_bundle(
        user_id=user_id,
        payload=BuildContextBundleCapabilityInput(
            context_type="course",
            context_id=course_id,
            context_meta={"thread_id": str(thread_id)},
            latest_user_text="Here is my answer: x = 4",
        ),
    )
    assert course_only_bundle.active_chat_probe is None


@pytest.mark.asyncio
async def test_submit_concept_probe_result_grades_persists_and_blocks_duplicates(  # noqa: PLR0915
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_id = uuid.uuid4()
    course_id = uuid.uuid4()
    concept_id = uuid.uuid4()
    lesson_id = uuid.uuid4()
    thread_id = uuid.uuid4()
    active_probe_id = uuid.uuid4()
    attacker_id = uuid.uuid4()

    await _ensure_user(db_session, user_id)
    await _ensure_user(db_session, attacker_id)
    db_session.add_all(
        [
            Course(
                id=course_id,
                user_id=user_id,
                title="Adaptive Submit Probe Course",
                description="Submit active probes.",
                adaptive_enabled=True,
            ),
            Concept(
                id=concept_id,
                domain="math",
                slug=f"submit-chat-probe-{concept_id}",
                name="Linear Equations",
                description="Solve equations.",
            ),
            CourseConcept(course_id=course_id, concept_id=concept_id, order_hint=1),
            Lesson(
                id=lesson_id,
                course_id=course_id,
                concept_id=concept_id,
                title="Solve Equations",
                description="Practice equations.",
                content="Practice body",
                order=1,
            ),
            UserConceptState(user_id=user_id, concept_id=concept_id, s_mastery=0.4, exposures=1),
            AssistantConversation(
                id=thread_id,
                user_id=user_id,
                context_type="course",
                context_id=course_id,
                context_meta={},
            ),
        ]
    )
    await db_session.flush()
    db_session.add(
        AssistantActiveProbe(
            id=active_probe_id,
            user_id=user_id,
            conversation_id=thread_id,
            course_id=course_id,
            concept_id=concept_id,
            lesson_id=lesson_id,
            question="Name the organelle that produces most cell energy.",
            expected_answer="mitochondria",
            answer_kind="text",
            hints=[],
            structure_signature="solve.linear.n",
            predicted_p_correct=0.61,
            target_probability=0.62,
            target_low=0.52,
            target_high=0.72,
            core_model="test-model",
        )
    )
    db_session.add(
        LearningQuestion(
            id=active_probe_id,
            user_id=user_id,
            course_id=course_id,
            concept_id=concept_id,
            lesson_id=lesson_id,
            question="Name the organelle that produces most cell energy.",
            expected_answer="mitochondria",
            answer_kind="text",
            grade_kind="practice_answer",
            expected_payload={},
            question_payload={
                "answerKind": "text",
                "probeFamily": "free_recall",
                "rendererKind": "free_form",
                "choices": [],
                "hints": [],
            },
            hints=[],
            structure_signature="solve.linear.n",
            predicted_p_correct=0.61,
            target_probability=0.62,
            target_low=0.52,
            target_high=0.72,
            core_model="test-model",
            practice_context="chat",
        )
    )
    await db_session.commit()

    async def fake_grade(self: object, request: object, user_id: uuid.UUID) -> GradeResponse:  # noqa: RUF029
        del self, user_id
        assert request.question == "Name the organelle that produces most cell energy."
        assert request.answer.answer_text == "mitochondria"
        return GradeResponse(
            is_correct=True,
            status="correct",
            feedback_markdown="Correct. The key answer is mitochondria.",
            verifier=VerifierInfo(name="llm"),
            tags=["mitochondria", "recall"],
        )

    monkeypatch.setattr("src.courses.services.grading_service.GradingService.grade", fake_grade)

    result = await LearningCapabilitiesFacade(db_session).execute_action_capability(
        user_id=user_id,
        capability_name="submit_concept_probe_result",
        payload={
            "course_id": str(course_id),
            "active_probe_id": str(active_probe_id),
            "learner_answer": "mitochondria",
            "thread_id": str(thread_id),
            "lesson_id": str(lesson_id),
        },
    )
    await db_session.commit()

    assert result["isCorrect"] is True
    assert result["feedbackMarkdown"] == (
        "Your answer was graded correct. The detailed answer is kept hidden so you can keep practicing."
    )
    assert "mitochondria" not in result["feedbackMarkdown"].lower()
    assert result["tags"] == []
    assert result["mastery"] > 0.4
    assert result["exposures"] == 2
    assert result["nextReviewAt"] is not None

    stored_probe = await db_session.scalar(select(AssistantActiveProbe).where(AssistantActiveProbe.id == active_probe_id))
    assert stored_probe is not None
    assert stored_probe.status == "answered"
    assert stored_probe.answered_correct is True
    assert stored_probe.answer_attempts == 1

    probe_event = await db_session.scalar(
        select(ProbeEvent).where(ProbeEvent.user_id == user_id, ProbeEvent.concept_id == concept_id)
    )
    assert probe_event is not None
    assert probe_event.context_tag == f"chat:{lesson_id}"
    assert probe_event.extra["question_id"] == str(active_probe_id)
    assert probe_event.extra["structure_signature"] == "solve.linear.n"

    duplicate = await LearningCapabilitiesFacade(db_session).execute_action_capability(
        user_id=user_id,
        capability_name="submit_concept_probe_result",
        payload={
            "course_id": str(course_id),
            "active_probe_id": str(active_probe_id),
            "learner_answer": "mitochondria",
            "thread_id": str(thread_id),
            "lesson_id": str(lesson_id),
        },
    )
    assert duplicate["reason"] is None
    assert duplicate["isCorrect"] is True

    other_thread_id = uuid.uuid4()
    db_session.add(
        AssistantConversation(
            id=other_thread_id,
            user_id=user_id,
            context_type="course",
            context_id=course_id,
            context_meta={},
        )
    )
    await db_session.commit()

    wrong_thread = await LearningCapabilitiesFacade(db_session).execute_action_capability(
        user_id=user_id,
        capability_name="submit_concept_probe_result",
        payload={
                "course_id": str(course_id),
                "active_probe_id": str(active_probe_id),
                "learner_answer": "mitochondria",
                "thread_id": str(other_thread_id),
            },
    )
    assert wrong_thread["reason"] == "active_probe_not_found"

    with pytest.raises(NotFoundError):
        await LearningCapabilitiesFacade(db_session).execute_action_capability(
            user_id=attacker_id,
            capability_name="submit_concept_probe_result",
            payload={
                "course_id": str(course_id),
                "active_probe_id": str(active_probe_id),
                "learner_answer": "mitochondria",
                "thread_id": str(thread_id),
                "lesson_id": str(lesson_id),
            },
        )

    second_active_probe_id = uuid.uuid4()
    db_session.add(
        AssistantActiveProbe(
            id=second_active_probe_id,
            user_id=user_id,
            conversation_id=thread_id,
            course_id=course_id,
            concept_id=concept_id,
            lesson_id=lesson_id,
            question="Name the organelle that produces most cell energy.",
            expected_answer="mitochondria",
            answer_kind="text",
            hints=[],
            structure_signature="recall.organelle",
            predicted_p_correct=0.61,
            target_probability=0.62,
            target_low=0.52,
            target_high=0.72,
            core_model="test-model",
        )
    )
    await db_session.commit()

    wrong_lesson = await LearningCapabilitiesFacade(db_session).execute_action_capability(
        user_id=user_id,
        capability_name="submit_concept_probe_result",
        payload={
            "course_id": str(course_id),
            "active_probe_id": str(second_active_probe_id),
            "learner_answer": "mitochondria",
            "thread_id": str(thread_id),
            "lesson_id": str(uuid.uuid4()),
        },
    )
    assert wrong_lesson["reason"] == "active_probe_not_found"


@pytest.mark.asyncio
async def test_practice_drill_generation_dedupes_recent_probe_history(db_session: AsyncSession) -> None:
    user_id = uuid.uuid4()
    course_id = uuid.uuid4()
    concept_id = uuid.uuid4()
    lesson_id = uuid.uuid4()
    captured_context: dict[str, str] = {}

    await _ensure_user(db_session, user_id)
    db_session.add(
        Course(
            id=course_id,
            user_id=user_id,
            title="Adaptive Dedupe Course",
            description="Avoid repeated drills.",
            adaptive_enabled=True,
        )
    )
    db_session.add(
        Concept(
            id=concept_id,
            domain="math",
            slug=f"dedupe-linear-equations-{course_id}",
            name="Linear Equations",
            description="Solve equations by inverse operations.",
        )
    )
    db_session.add(CourseConcept(course_id=course_id, concept_id=concept_id, order_hint=1))
    db_session.add(
        Lesson(
            id=lesson_id,
            course_id=course_id,
            concept_id=concept_id,
            title="Solve Equations",
            description="Practice solving equations.",
            content="Practice body",
            order=1,
        )
    )
    db_session.add(
        UserConceptState(
            user_id=user_id,
            concept_id=concept_id,
            s_mastery=0.42,
            exposures=2,
            next_review_at=datetime.now(UTC) - timedelta(minutes=3),
        )
    )
    db_session.add(
        ProbeEvent(
            user_id=user_id,
            concept_id=concept_id,
            rating=1,
            correct=False,
            extra={"question": "Solve 2x + 3 = 11.", "structure_signature": "solve.nx.n.n"},
        )
    )
    await db_session.flush()
    db_session.add(
        AssistantActiveProbe(
            user_id=user_id,
            course_id=course_id,
            concept_id=concept_id,
            lesson_id=lesson_id,
            question="Solve 5y - 2 = 18.",
            expected_answer="y = 4",
            answer_kind="latex",
            hints=[],
            structure_signature="solve.ny.n.n",
            predicted_p_correct=0.63,
            target_probability=0.62,
            target_low=0.52,
            target_high=0.72,
            core_model="test-model",
        )
    )
    await db_session.commit()

    class FakePracticeLLM:
        async def generate_practice_question_batch(self, **kwargs: object) -> object:
            captured_context["learner_context"] = str(kwargs["learner_context"])
            return SimpleNamespace(
                questions=[
                    SimpleNamespace(question="Solve 2x + 3 = 11.", expected_answer="x = 4", answer_kind="latex"),
                    SimpleNamespace(question="Solve 5y - 2 = 18.", expected_answer="y = 4", answer_kind="latex"),
                    SimpleNamespace(question="Solve 7z + 1 = 22.", expected_answer="z = 3", answer_kind="latex"),
                ]
            )

        async def predict_practice_correctness_batch(self, **_kwargs: object) -> object:
            return SimpleNamespace(predicted_p_correct=[0.62, 0.63, 0.64])

    drills = await PracticeDrillService(db_session, llm_client=FakePracticeLLM()).generate_drills(
        user_id=user_id,
        course_id=course_id,
        concept_id=concept_id,
        count=1,
        learner_context="Learner said they add four to both quantities.",
    )

    assert drills[0].question == "Solve 7z + 1 = 22."
    assert drills[0].structure_signature != "solve.nx.n.n"
    assert drills[0].structure_signature != "solve.ny.n.n"
    assert "(mid)" not in captured_context["learner_context"]
    assert "OVERDUE" not in captured_context["learner_context"]
    assert "Due for review: true" in captured_context["learner_context"]
    assert "Learner chat context: Learner said they add four to both quantities." in captured_context["learner_context"]


def test_chat_request_accepts_assistant_ui_context_aliases() -> None:
    course_id = uuid.uuid4()
    lesson_id = uuid.uuid4()

    request = ChatRequest.model_validate(
        {
            "threadId": str(uuid.uuid4()),
            "contextType": "course",
            "contextId": str(course_id),
            "contextMeta": {"lesson_id": str(lesson_id)},
            "pendingQuote": "selected phrase",
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "Explain this part."}],
                }
            ],
        }
    )

    assert request.context_type == "course"
    assert request.context_id == course_id
    assert request.context_meta == {"lesson_id": str(lesson_id)}
    assert request.pending_quote == "selected phrase"
