"""Top-level grading engine.

Wires the metric calculator, scorer, and aggregators together. The output
mirrors REQUIREMENTS §5.2 — `compute_grades` returns a typed result; pair
it with `to_payload` to get the JSONB-shaped dict that gets written into
`snapshots.grades`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.services.grading.aggregator import (
    aggregate_general_grade,
    aggregate_sub_grade,
)
from app.services.grading.metrics import SUB_GRADE_METRICS
from app.services.grading.types import GradingInputs, GradingResult, SubGradeResult


def compute_grades(inputs: GradingInputs) -> GradingResult:
    sub_grade_results: dict[str, SubGradeResult] = {}
    for sub_grade_name, metric_funcs in SUB_GRADE_METRICS.items():
        weights = inputs.sub_grade_weights.get(sub_grade_name, {})
        if not weights:
            sub_grade_results[sub_grade_name] = SubGradeResult(
                score=None, metrics_used=0, metrics_total=0
            )
            continue

        # Compute raw values only for the metrics this sub-grade actually
        # weights — keeps work proportional to the configuration.
        raw_values = {
            metric_name: metric_funcs[metric_name](inputs)
            for metric_name in weights
            if metric_name in metric_funcs
        }
        sub_grade_results[sub_grade_name] = aggregate_sub_grade(
            metric_values=raw_values,
            metric_weights=weights,
            thresholds=inputs.grade_thresholds,
        )

    general = aggregate_general_grade(sub_grade_results, inputs.general_grade_weights)
    return GradingResult(general=general, sub_grades=sub_grade_results)


def to_payload(result: GradingResult) -> dict[str, Any]:
    """Serialise a `GradingResult` into the JSONB shape from REQUIREMENTS §5.2.

    Decimals are coerced to floats so the dict is directly json-encodable.
    "Incomplete" sub-grades surface as `score: null` so the UI can branch.
    """
    return {
        "general": _maybe_float(result.general),
        "sub_grades": {
            name: {
                "score": _maybe_float(sg.score),
                "metrics_used": sg.metrics_used,
                "metrics_total": sg.metrics_total,
                "breakdown": {
                    metric: {
                        "value": _maybe_float(b.value),
                        "score": b.score,
                    }
                    for metric, b in sg.breakdown.items()
                },
            }
            for name, sg in result.sub_grades.items()
        },
    }


def _maybe_float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None
