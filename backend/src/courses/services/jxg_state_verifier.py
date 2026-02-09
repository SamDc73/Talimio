"""Deterministic verifier for JSXGraph board-state answers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from src.courses.schemas import GradeStatus, JXGBoardState


_DEFAULT_TOLERANCE = 0.05
_NEAR_BOUNDARY_RATIO = 0.8


@dataclass(frozen=True)
class JXGStateVerificationResult:
    """Verification outcome for JSXGraph board state grading."""

    is_correct: bool
    status: GradeStatus
    method: str | None
    notes: str | None
    tags: list[str]
    feedback_metadata: dict[str, Any]


class JXGStateVerifier:
    """Compare expected and answer board states with tolerance checks."""

    def verify(
        self,
        expected_state: JXGBoardState,
        answer_state: JXGBoardState,
        tolerance: float | None = None,
        per_check_tolerance: dict[str, float] | None = None,
    ) -> JXGStateVerificationResult:
        """Verify answer state against expected state."""
        global_tolerance = tolerance if tolerance is not None else _DEFAULT_TOLERANCE
        tolerance_overrides = per_check_tolerance or {}

        checks: list[dict[str, Any]] = []
        checks.extend(self._check_points(expected_state, answer_state, global_tolerance, tolerance_overrides))
        checks.extend(self._check_sliders(expected_state, answer_state, global_tolerance, tolerance_overrides))
        checks.extend(self._check_curves(expected_state, answer_state, global_tolerance, tolerance_overrides))

        failed_checks = [check for check in checks if not check["isCorrect"]]
        near_boundary_checks = [check for check in checks if check["isCorrect"] and check["isNearBoundary"]]

        tags: list[str] = []
        if failed_checks:
            tags.append("graph-out-of-tolerance")
        if near_boundary_checks:
            tags.append("graph-near-boundary")
        if any(check.get("actualMissing") for check in checks):
            tags.append("graph-missing-value")

        is_correct = len(failed_checks) == 0
        status: GradeStatus = "correct" if is_correct else "incorrect"

        notes = None
        if is_correct and near_boundary_checks:
            notes = "Correct within tolerance; some values are near the tolerance boundary."
        if not is_correct:
            notes = "One or more graph checks are outside tolerance."

        metadata = {
            "summary": {
                "totalChecks": len(checks),
                "failedChecks": len(failed_checks),
                "nearBoundaryChecks": len(near_boundary_checks),
                "globalTolerance": global_tolerance,
            },
            "checks": checks,
        }

        return JXGStateVerificationResult(
            is_correct=is_correct,
            status=status,
            method="tolerance_distance",
            notes=notes,
            tags=tags,
            feedback_metadata=metadata,
        )

    def _check_points(
        self,
        expected_state: JXGBoardState,
        answer_state: JXGBoardState,
        global_tolerance: float,
        tolerance_overrides: dict[str, float],
    ) -> list[dict[str, Any]]:
        checks: list[dict[str, Any]] = []
        for point_id, expected_value in expected_state.points.items():
            check_id = f"point:{point_id}"
            tolerance = self._resolve_tolerance(check_id, global_tolerance, tolerance_overrides)
            actual_value = answer_state.points.get(point_id)

            if actual_value is None:
                checks.append(
                    {
                        "checkId": check_id,
                        "kind": "point",
                        "isCorrect": False,
                        "isNearBoundary": False,
                        "actualMissing": True,
                        "tolerance": tolerance,
                        "expected": {"x": expected_value[0], "y": expected_value[1]},
                        "actual": None,
                        "delta": None,
                        "deltaX": None,
                        "deltaY": None,
                        "offBy": None,
                    }
                )
                continue

            delta_x = abs(actual_value[0] - expected_value[0])
            delta_y = abs(actual_value[1] - expected_value[1])
            delta = math.hypot(delta_x, delta_y)
            off_by = max(0.0, delta - tolerance)
            is_correct = delta <= tolerance

            checks.append(
                {
                    "checkId": check_id,
                    "kind": "point",
                    "isCorrect": is_correct,
                    "isNearBoundary": is_correct and self._is_near_boundary(delta, tolerance),
                    "actualMissing": False,
                    "tolerance": tolerance,
                    "expected": {"x": expected_value[0], "y": expected_value[1]},
                    "actual": {"x": actual_value[0], "y": actual_value[1]},
                    "delta": delta,
                    "deltaX": delta_x,
                    "deltaY": delta_y,
                    "offBy": off_by,
                }
            )
        return checks

    def _check_sliders(
        self,
        expected_state: JXGBoardState,
        answer_state: JXGBoardState,
        global_tolerance: float,
        tolerance_overrides: dict[str, float],
    ) -> list[dict[str, Any]]:
        checks: list[dict[str, Any]] = []
        for slider_id, expected_value in expected_state.sliders.items():
            check_id = f"slider:{slider_id}"
            tolerance = self._resolve_tolerance(check_id, global_tolerance, tolerance_overrides)
            actual_value = answer_state.sliders.get(slider_id)

            if actual_value is None:
                checks.append(
                    {
                        "checkId": check_id,
                        "kind": "slider",
                        "isCorrect": False,
                        "isNearBoundary": False,
                        "actualMissing": True,
                        "tolerance": tolerance,
                        "expected": expected_value,
                        "actual": None,
                        "delta": None,
                        "offBy": None,
                    }
                )
                continue

            delta = abs(actual_value - expected_value)
            off_by = max(0.0, delta - tolerance)
            is_correct = delta <= tolerance

            checks.append(
                {
                    "checkId": check_id,
                    "kind": "slider",
                    "isCorrect": is_correct,
                    "isNearBoundary": is_correct and self._is_near_boundary(delta, tolerance),
                    "actualMissing": False,
                    "tolerance": tolerance,
                    "expected": expected_value,
                    "actual": actual_value,
                    "delta": delta,
                    "offBy": off_by,
                }
            )
        return checks

    def _check_curves(
        self,
        expected_state: JXGBoardState,
        answer_state: JXGBoardState,
        global_tolerance: float,
        tolerance_overrides: dict[str, float],
    ) -> list[dict[str, Any]]:
        checks: list[dict[str, Any]] = []
        for curve_id, expected_samples in expected_state.curves.items():
            check_id = f"curve:{curve_id}"
            tolerance = self._resolve_tolerance(check_id, global_tolerance, tolerance_overrides)
            actual_samples = answer_state.curves.get(curve_id)

            if actual_samples is None:
                checks.append(
                    {
                        "checkId": check_id,
                        "kind": "curve",
                        "isCorrect": False,
                        "isNearBoundary": False,
                        "actualMissing": True,
                        "tolerance": tolerance,
                        "expectedSampleCount": len(expected_samples),
                        "actualSampleCount": 0,
                        "maxDelta": None,
                        "offBy": None,
                    }
                )
                continue

            if len(actual_samples) != len(expected_samples):
                checks.append(
                    {
                        "checkId": check_id,
                        "kind": "curve",
                        "isCorrect": False,
                        "isNearBoundary": False,
                        "actualMissing": False,
                        "tolerance": tolerance,
                        "expectedSampleCount": len(expected_samples),
                        "actualSampleCount": len(actual_samples),
                        "maxDelta": None,
                        "offBy": None,
                    }
                )
                continue

            deltas: list[float] = []
            for expected_sample, actual_sample in zip(expected_samples, actual_samples, strict=False):
                delta_x = actual_sample[0] - expected_sample[0]
                delta_y = actual_sample[1] - expected_sample[1]
                deltas.append(math.hypot(delta_x, delta_y))

            max_delta = max(deltas, default=0.0)
            off_by = max(0.0, max_delta - tolerance)
            is_correct = max_delta <= tolerance

            checks.append(
                {
                    "checkId": check_id,
                    "kind": "curve",
                    "isCorrect": is_correct,
                    "isNearBoundary": is_correct and self._is_near_boundary(max_delta, tolerance),
                    "actualMissing": False,
                    "tolerance": tolerance,
                    "expectedSampleCount": len(expected_samples),
                    "actualSampleCount": len(actual_samples),
                    "maxDelta": max_delta,
                    "offBy": off_by,
                }
            )
        return checks

    def _resolve_tolerance(
        self,
        check_id: str,
        global_tolerance: float,
        tolerance_overrides: dict[str, float],
    ) -> float:
        candidate = tolerance_overrides.get(check_id, global_tolerance)
        return candidate if candidate >= 0 else global_tolerance

    def _is_near_boundary(self, delta: float, tolerance: float) -> bool:
        if tolerance <= 0:
            return delta == 0
        return delta >= (tolerance * _NEAR_BOUNDARY_RATIO)
