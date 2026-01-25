"""SymPy-based verifier for LaTeX expressions."""

from __future__ import annotations

from dataclasses import dataclass

import sympy
from latex2sympy2_extended import latex2sympy
from sympy.core.relational import Equality, Relational

from src.courses.schemas import GradeStatus
from src.courses.services.latex_expression_sampling import numeric_equivalence


_MAX_SAMPLE_COMBOS = 8
_DEFAULT_TOLERANCE = 1e-6


@dataclass(frozen=True)
class LatexExpressionVerificationDiagnostics:
    """Diagnostics emitted by the LaTeX expression verifier."""

    expected_parse_error: str | None
    answer_parse_error: str | None
    method_attempts: list[str]
    numeric_samples: int
    likely_mistake: str | None


@dataclass(frozen=True)
class LatexExpressionVerificationResult:
    """Verification outcome including status and diagnostics."""

    is_correct: bool
    status: GradeStatus
    method: str | None
    notes: str | None
    diagnostics: LatexExpressionVerificationDiagnostics
    tags: list[str]


class LatexExpressionVerifier:
    """Deterministic SymPy verifier for LaTeX expressions."""

    def __init__(self, *, tolerance: float = _DEFAULT_TOLERANCE, max_samples: int = _MAX_SAMPLE_COMBOS) -> None:
        self._tolerance = tolerance
        self._max_samples = max_samples

    def verify(self, expected_latex: str, answer_latex: str) -> LatexExpressionVerificationResult:
        """Verify whether the answer matches the expected expression."""
        expected_expr, expected_error = self._parse_latex(expected_latex)
        answer_expr, answer_error = self._parse_latex(answer_latex)

        method_attempts: list[str] = []
        tags: list[str] = []

        if expected_error or answer_error or expected_expr is None or answer_expr is None:
            if expected_error or expected_expr is None:
                tags.append("expected-parse-error")
            if answer_error or answer_expr is None:
                tags.append("answer-parse-error")
            diagnostics = LatexExpressionVerificationDiagnostics(
                expected_parse_error=expected_error or ("Parser returned None" if expected_expr is None else None),
                answer_parse_error=answer_error or ("Parser returned None" if answer_expr is None else None),
                method_attempts=method_attempts,
                numeric_samples=0,
                likely_mistake="parse-error",
            )
            notes = "Failed to parse expected or answer expression." if expected_error or answer_error else "Parsed expression missing."
            return LatexExpressionVerificationResult(
                is_correct=False,
                status="parse_error",
                method=None,
                notes=notes,
                diagnostics=diagnostics,
                tags=tags,
            )

        if self._is_unsupported_relation(expected_expr) or self._is_unsupported_relation(answer_expr):
            diagnostics = LatexExpressionVerificationDiagnostics(
                expected_parse_error=None,
                answer_parse_error=None,
                method_attempts=method_attempts,
                numeric_samples=0,
                likely_mistake="unsupported-relation",
            )
            notes = "Relational operators are not supported yet."
            return LatexExpressionVerificationResult(
                is_correct=False,
                status="unsupported",
                method=None,
                notes=notes,
                diagnostics=diagnostics,
                tags=[*tags, "unsupported-relation"],
            )

        normalized_expected, expected_equation = self._normalize_expression(expected_expr)
        normalized_answer, answer_equation = self._normalize_expression(answer_expr)
        allow_sign_flip = expected_equation and answer_equation

        diff_expr = sympy.simplify(normalized_expected - normalized_answer)
        sum_expr = sympy.simplify(normalized_expected + normalized_answer) if allow_sign_flip else None

        method_attempts.append("simplify")
        if self._is_zero(diff_expr) or (allow_sign_flip and sum_expr is not None and self._is_zero(sum_expr)):
            diagnostics = self._build_diagnostics(method_attempts, 0, normalized_expected, normalized_answer)
            return LatexExpressionVerificationResult(
                is_correct=True,
                status="correct",
                method="simplify",
                notes=None,
                diagnostics=diagnostics,
                tags=tags,
            )

        method_attempts.append("equals")
        if self._equals_zero(diff_expr) or (allow_sign_flip and sum_expr is not None and self._equals_zero(sum_expr)):
            diagnostics = self._build_diagnostics(method_attempts, 0, normalized_expected, normalized_answer)
            return LatexExpressionVerificationResult(
                is_correct=True,
                status="correct",
                method="equals",
                notes=None,
                diagnostics=diagnostics,
                tags=tags,
            )

        method_attempts.append("numeric_sampling")
        numeric_result, numeric_samples = numeric_equivalence(
            diff_expr,
            sum_expr,
            allow_sign_flip,
            tolerance=self._tolerance,
            max_samples=self._max_samples,
        )
        diagnostics = self._build_diagnostics(method_attempts, numeric_samples, normalized_expected, normalized_answer)

        if numeric_result is True:
            return LatexExpressionVerificationResult(
                is_correct=True,
                status="correct",
                method="numeric_sampling",
                notes=None,
                diagnostics=diagnostics,
                tags=tags,
            )

        notes = "Numeric sampling did not establish equivalence." if numeric_samples > 0 else "No valid samples found."
        return LatexExpressionVerificationResult(
            is_correct=False,
            status="incorrect",
            method="numeric_sampling",
            notes=notes,
            diagnostics=diagnostics,
            tags=tags + self._build_mistake_tags(diagnostics.likely_mistake),
        )

    def _parse_latex(self, value: str) -> tuple[sympy.Expr | Relational | None, str | None]:
        try:
            parsed = latex2sympy(value)
        except Exception as exc:
            return None, str(exc)
        return parsed, None

    def _normalize_expression(self, expr: sympy.Expr | Relational) -> tuple[sympy.Expr, bool]:
        if isinstance(expr, Relational):
            return sympy.simplify(expr.lhs - expr.rhs), True
        return expr, False

    def _is_unsupported_relation(self, expr: sympy.Expr | Relational) -> bool:
        if not isinstance(expr, Relational):
            return False
        return not isinstance(expr, Equality)

    def _is_zero(self, expr: sympy.Expr) -> bool:
        if expr.is_zero is True:
            return True
        if expr.is_zero is False:
            return False
        return False

    def _equals_zero(self, expr: sympy.Expr) -> bool:
        try:
            return bool(expr.equals(0))
        except Exception:  # pragma: no cover - sympy equality can raise on edge cases
            return False

    def _build_diagnostics(
        self,
        method_attempts: list[str],
        numeric_samples: int,
        expected_expr: sympy.Expr,
        answer_expr: sympy.Expr,
    ) -> LatexExpressionVerificationDiagnostics:
        likely_mistake = None
        try:
            if self._is_zero(sympy.simplify(expected_expr + answer_expr)):
                likely_mistake = "sign-error"
            elif not sympy.simplify(expected_expr - answer_expr).free_symbols:
                likely_mistake = "constant-offset"
        except Exception:
            likely_mistake = None

        return LatexExpressionVerificationDiagnostics(
            expected_parse_error=None,
            answer_parse_error=None,
            method_attempts=method_attempts,
            numeric_samples=numeric_samples,
            likely_mistake=likely_mistake,
        )

    def _build_mistake_tags(self, likely_mistake: str | None) -> list[str]:
        if not likely_mistake:
            return []
        return [likely_mistake]
