"""Numeric sampling helpers for LaTeX expression verification."""

from __future__ import annotations

import math
from itertools import islice, product

import sympy


_SAMPLE_VALUES = (
    sympy.Integer(-2),
    sympy.Integer(-1),
    sympy.Rational(-1, 2),
    sympy.Rational(1, 2),
    sympy.Integer(1),
    sympy.Integer(2),
    sympy.Integer(3),
)


def numeric_equivalence(
    diff_expr: sympy.Expr,
    sum_expr: sympy.Expr | None,
    allow_sign_flip: bool,
    *,
    tolerance: float,
    max_samples: int,
) -> tuple[bool | None, int]:
    """Check numeric equivalence by sampling symbol assignments."""
    symbols = sorted(diff_expr.free_symbols, key=lambda symbol: symbol.name)
    if not symbols:
        return _constant_equivalence(diff_expr, sum_expr, allow_sign_flip, tolerance=tolerance)

    diff_valid = 0
    sum_valid = 0
    diff_matches = True
    sum_matches = True

    result: bool | None = None
    samples = 0

    for values in islice(product(_SAMPLE_VALUES, repeat=len(symbols)), max_samples):
        subs = dict(zip(symbols, values, strict=True))
        diff_value = _evaluate_numeric(diff_expr, subs)
        sum_value = _evaluate_numeric(sum_expr, subs) if allow_sign_flip and sum_expr is not None else None

        if diff_value is not None:
            diff_valid += 1
            diff_matches = diff_matches and abs(diff_value) <= tolerance
        if allow_sign_flip and sum_value is not None:
            sum_valid += 1
            sum_matches = sum_matches and abs(sum_value) <= tolerance

        if not allow_sign_flip:
            if diff_valid > 0 and not diff_matches:
                result = False
                samples = diff_valid
                break
        elif diff_valid > 0 and sum_valid > 0 and not diff_matches and not sum_matches:
            result = False
            samples = max(diff_valid, sum_valid)
            break

    if result is None:
        if diff_valid == 0 and sum_valid == 0:
            result = None
            samples = 0
        elif diff_valid > 0 and diff_matches:
            result = True
            samples = diff_valid
        elif sum_valid > 0 and sum_matches:
            result = True
            samples = sum_valid
        else:
            result = False
            samples = max(diff_valid, sum_valid)

    return result, samples


def _constant_equivalence(
    diff_expr: sympy.Expr,
    sum_expr: sympy.Expr | None,
    allow_sign_flip: bool,
    *,
    tolerance: float,
) -> tuple[bool | None, int]:
    diff_value = _evaluate_numeric(diff_expr, {})
    if diff_value is not None and abs(diff_value) <= tolerance:
        return True, 1
    if allow_sign_flip and sum_expr is not None:
        sum_value = _evaluate_numeric(sum_expr, {})
        if sum_value is not None and abs(sum_value) <= tolerance:
            return True, 1
    if diff_value is None and (sum_expr is None or _evaluate_numeric(sum_expr, {}) is None):
        return None, 0
    return False, 1


def _evaluate_numeric(
    expr: sympy.Expr | None,
    subs: dict[sympy.Basic | int | float | complex, sympy.Expr | int | float | complex],
) -> complex | None:
    if expr is None:
        return None
    try:
        evaluated = expr.subs(subs)
        if evaluated.free_symbols:
            return None
        numeric = complex(evaluated.evalf())
    except Exception:
        return None
    if not math.isfinite(numeric.real) or not math.isfinite(numeric.imag):
        return None
    return numeric
