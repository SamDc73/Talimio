"""Grading service backed by deterministic verifiers (SymPy for LaTeX expressions) and optional LLM coaching."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict
from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel, ConfigDict, Field

from src.ai.client import LLMClient
from src.ai.prompts import GRADING_COACH_PROMPT
from src.config.settings import get_settings
from src.courses.schemas import GradeErrorHighlight, GradeRequest, GradeResponse, VerifierInfo
from src.courses.services.jxg_state_verifier import JXGStateVerifier
from src.courses.services.latex_expression_verifier import (
    LatexExpressionVerificationResult,
    LatexExpressionVerifier,
)


def _to_camel(string: str) -> str:
    parts = string.split("_")
    if len(parts) == 1:
        return string
    head, *tail = parts
    return head + "".join(word.capitalize() for word in tail)


class GradingCoachFeedback(BaseModel):
    """Structured output from the grading coach LLM."""

    feedback_markdown: str = Field(..., min_length=1)
    tags: list[str] = Field(default_factory=list)
    error_highlight: GradeErrorHighlight | None = None

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True, extra="forbid")


ALLOWED_GRADING_TAGS = {
    "answer-parse-error",
    "calculation-error",
    "constant-offset",
    "distribution",
    "expected-parse-error",
    "missing-term",
    "notation-error",
    "parse-error",
    "sign-error",
    "simplification",
    "unsupported-relation",
}

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class GradingService:
    """Grade deterministic practice answers and generate feedback."""

    def __init__(self, session: AsyncSession) -> None:
        self._verifier = LatexExpressionVerifier()
        self._jxg_state_verifier = JXGStateVerifier()
        self._llm_client = LLMClient()
        self._session = session
        self._logger = logging.getLogger(__name__)

    async def grade(self, request: GradeRequest, user_id: uuid.UUID) -> GradeResponse:
        """Grade a learner answer and return feedback."""
        if request.kind == "latex_expression":
            return await self._grade_latex_expression(request, user_id)

        if request.kind == "jxg_state":
            return self._grade_jxg_state(request)

        fallback = self._fallback_feedback("unsupported", request.expected.criteria)
        verifier = VerifierInfo(name="sympy", method=None, notes="Unsupported grading kind.")
        return GradeResponse(
            is_correct=False,
            status="unsupported",
            feedback_markdown=fallback,
            verifier=verifier,
            tags=["unsupported-kind"],
        )

    async def _grade_latex_expression(self, request: GradeRequest, user_id: uuid.UUID) -> GradeResponse:
        expected_latex = request.expected.expected_latex
        answer_latex = request.answer.answer_latex
        if expected_latex is None or answer_latex is None:
            fallback = self._fallback_feedback("parse_error", request.expected.criteria)
            verifier = VerifierInfo(name="sympy", method=None, notes="Missing LaTeX payload.")
            return GradeResponse(
                is_correct=False,
                status="parse_error",
                feedback_markdown=fallback,
                verifier=verifier,
                tags=["parse-error"],
            )

        verification = self._verifier.verify(expected_latex, answer_latex)
        feedback_markdown, coach_tags, error_highlight = await self._generate_feedback(
            request=request,
            verification=verification,
            user_id=user_id,
        )

        merged_tags = self._merge_tags(verification.tags, coach_tags)
        fallback = self._fallback_feedback(verification.status, request.expected.criteria)
        final_feedback = feedback_markdown or fallback

        verifier = VerifierInfo(
            name="sympy",
            method=verification.method,
            notes=verification.notes,
        )
        return GradeResponse(
            is_correct=verification.is_correct,
            status=verification.status,
            feedback_markdown=final_feedback,
            verifier=verifier,
            tags=merged_tags,
            error_highlight=error_highlight,
        )

    def _grade_jxg_state(self, request: GradeRequest) -> GradeResponse:
        expected_state = request.expected.expected_state
        answer_state = request.answer.answer_state
        if expected_state is None or answer_state is None:
            fallback = "Graph-state payload is incomplete. Provide expectedState and answerState."
            verifier = VerifierInfo(name="jxg_state", method=None, notes="Missing graph-state payload.")
            return GradeResponse(
                is_correct=False,
                status="parse_error",
                feedback_markdown=fallback,
                verifier=verifier,
                tags=["graph-parse-error"],
            )

        verification = self._jxg_state_verifier.verify(
            expected_state=expected_state,
            answer_state=answer_state,
            tolerance=request.expected.tolerance,
            per_check_tolerance=request.expected.per_check_tolerance,
        )
        feedback_markdown = self._build_graph_feedback(verification.feedback_metadata, verification.is_correct)
        verifier = VerifierInfo(
            name="jxg_state",
            method=verification.method,
            notes=verification.notes,
        )
        return GradeResponse(
            is_correct=verification.is_correct,
            status=verification.status,
            feedback_markdown=feedback_markdown,
            verifier=verifier,
            tags=verification.tags,
            feedback_metadata=verification.feedback_metadata,
        )

    async def _generate_feedback(
        self,
        request: GradeRequest,
        verification: LatexExpressionVerificationResult,
        user_id: uuid.UUID,
    ) -> tuple[str | None, list[str], GradeErrorHighlight | None]:
        settings = get_settings()
        model = settings.GRADING_COACH_LLM_MODEL
        if not model:
            try:
                model = settings.primary_llm_model
                self._logger.info("GRADING_COACH_LLM_MODEL not set; falling back to PRIMARY_LLM_MODEL: %s", model)
            except Exception:
                return None, [], None

        payload = {
            "question": request.question,
            "expectedLatex": request.expected.expected_latex,
            "answerLatex": request.answer.answer_latex,
            "criteria": request.expected.criteria,
            "hintsUsed": request.context.hints_used,
            "verifierVerdict": {
                "isCorrect": verification.is_correct,
                "status": verification.status,
                "method": verification.method,
                "notes": verification.notes,
            },
            "verifierDiagnostics": asdict(verification.diagnostics),
        }
        messages = [
            {"role": "system", "content": GRADING_COACH_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
        ]

        try:
            result = await self._llm_client.get_completion(
                messages=messages,
                response_model=GradingCoachFeedback,
                temperature=0,
                user_id=user_id,
                model=model,
            )
        except Exception:
            self._logger.exception("Grading coach LLM feedback failed.")
            return None, [], None

        if not isinstance(result, GradingCoachFeedback):
            return None, [], None
        return result.feedback_markdown, result.tags, result.error_highlight

    def _fallback_feedback(self, status: str, criteria: str | None) -> str:
        criteria_note = f" Focus on: {criteria}." if criteria else ""
        if status == "correct":
            return f"Nice work — your expression matches the expected result.{criteria_note}"
        if status == "parse_error":
            return "I couldn't parse the LaTeX in your response. Check parentheses, braces, and symbols."
        if status == "unsupported":
            return "This response type is not supported yet. Try another practice item."
        return f"Not quite. Re-check your work and simplify carefully.{criteria_note}"

    def _merge_tags(self, *tag_sets: list[str]) -> list[str]:
        seen: set[str] = set()
        merged: list[str] = []
        for tag_list in tag_sets:
            for tag in tag_list:
                normalized = tag.strip().lower()
                if not normalized or normalized in seen:
                    continue
                if normalized not in ALLOWED_GRADING_TAGS:
                    continue
                seen.add(normalized)
                merged.append(normalized)
        return merged

    def _build_graph_feedback(self, metadata: dict[str, object], is_correct: bool) -> str:
        checks_data = metadata.get("checks")
        checks: list[dict[str, Any]] = []
        if isinstance(checks_data, list):
            checks.extend(cast("dict[str, Any]", check) for check in checks_data if isinstance(check, dict))

        failed = [check for check in checks if not bool(check.get("isCorrect", False))]
        near_boundary = [check for check in checks if bool(check.get("isNearBoundary", False))]

        if is_correct:
            if not near_boundary:
                return "Correct. Your board state matches the expected values within tolerance."
            max_delta = 0.0
            for check in near_boundary:
                delta = check.get("delta") or check.get("maxDelta") or 0.0
                if isinstance(delta, (int, float)):
                    max_delta = max(max_delta, float(delta))
            return (
                "Correct within tolerance. Some values are close to the boundary "
                f"(largest delta: {max_delta:.4f})."
            )

        if not failed:
            return "Not quite. Some graph checks are outside tolerance."

        first_failed = failed[0]
        check_id = str(first_failed.get("checkId", "check"))
        off_by = first_failed.get("offBy")
        off_by_note = f" Off by {off_by:.4f}." if isinstance(off_by, (int, float)) else ""
        return f"Not quite. `{check_id}` is outside tolerance.{off_by_note}"
