"""Grading service backed by deterministic verifiers (SymPy for LaTeX expressions) and optional LLM coaching."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from src.ai.client import LLMClient
from src.ai.prompts import GRADING_COACH_PROMPT
from src.config.settings import get_settings
from src.courses.schemas import GradeErrorHighlight, GradeRequest, GradeResponse, VerifierInfo
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
    """Grade LaTeX expressions and generate feedback."""

    def __init__(self, session: AsyncSession) -> None:
        self._verifier = LatexExpressionVerifier()
        self._llm_client = LLMClient()
        self._session = session
        self._logger = logging.getLogger(__name__)

    async def grade(self, request: GradeRequest, user_id: uuid.UUID) -> GradeResponse:
        """Grade a LaTeX expression answer and return feedback."""
        if request.kind != "latex_expression":
            fallback = self._fallback_feedback("unsupported", request.expected.criteria)
            verifier = VerifierInfo(name="sympy", method=None, notes="Unsupported grading kind.")
            return GradeResponse(
                is_correct=False,
                status="unsupported",
                feedback_markdown=fallback,
                verifier=verifier,
                tags=["unsupported-kind"],
            )

        verification = self._verifier.verify(request.expected.expected_latex, request.answer.answer_latex)
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
                session=self._session,
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
