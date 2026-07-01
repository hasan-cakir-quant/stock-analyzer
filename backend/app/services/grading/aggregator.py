"""Aggregators — fold per-metric scores into sub-grades, and sub-grades into the general grade.

Renormalisation rule (FR-3.4.6.1): when a metric is missing, its weight is
removed and the remaining weights are re-scaled to sum to whatever they
sum to — equivalent to a weighted average over only the metrics we have.

A sub-grade with **zero** scoreable metrics returns `score=None`, which the
UI renders as "Incomplete" (FR-3.4.6.3).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.services.grading.scorer import score_metric
from app.services.grading.types import MetricBreakdown, SubGradeResult


def _to_decimal(raw: Any) -> Decimal:
    return raw if isinstance(raw, Decimal) else Decimal(str(raw))


def aggregate_sub_grade(
    metric_values: dict[str, Decimal | None],
    metric_weights: dict[str, Decimal],
    thresholds: dict[str, dict[str, Any]],
) -> SubGradeResult:
    """Build one sub-grade result from raw metric values + weights + thresholds."""
    breakdown: dict[str, MetricBreakdown] = {}
    weight_sum = Decimal(0)
    weighted_score_sum = Decimal(0)
    metrics_used = 0

    for metric_name, weight in metric_weights.items():
        value = metric_values.get(metric_name)
        breakdown[metric_name] = MetricBreakdown(value=value, score=None)
        if value is None:
            continue
        threshold = thresholds.get(metric_name)
        if threshold is None:
            continue
        score = score_metric(value, threshold)
        if score is None:
            continue

        breakdown[metric_name].score = score
        weight_dec = _to_decimal(weight)
        weight_sum += weight_dec
        weighted_score_sum += Decimal(score) * weight_dec
        metrics_used += 1

    if metrics_used == 0 or weight_sum == 0:
        return SubGradeResult(
            score=None,
            metrics_used=0,
            metrics_total=len(metric_weights),
            breakdown=breakdown,
        )

    final_score = weighted_score_sum / weight_sum
    return SubGradeResult(
        score=final_score,
        metrics_used=metrics_used,
        metrics_total=len(metric_weights),
        breakdown=breakdown,
    )


def aggregate_general_grade(
    sub_grades: dict[str, SubGradeResult], general_weights: dict[str, Decimal]
) -> Decimal | None:
    """Weighted average of sub-grade scores; missing sub-grades drop out and
    the remaining weights renormalise."""
    weight_sum = Decimal(0)
    weighted = Decimal(0)
    for sub_grade_name, weight in general_weights.items():
        result = sub_grades.get(sub_grade_name)
        if result is None or result.score is None:
            continue
        weight_dec = _to_decimal(weight)
        weight_sum += weight_dec
        weighted += result.score * weight_dec

    if weight_sum == 0:
        return None
    return weighted / weight_sum
