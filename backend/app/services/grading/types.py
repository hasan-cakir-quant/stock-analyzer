"""Value types for the grading engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.services.valuations.types import Quarter


@dataclass(slots=True)
class GradingInputs:
    """Everything the grading engine needs in one place.

    `parameters` is the merged Parameter Panel state; we read e.g. `beta`
    from there. `average_fair_value` is `summarize(...)["average"]` from
    the valuation registry — it powers the price-vs-fair-value metric.

    Settings are split out (rather than passed as a dict-of-dicts) so the
    engine surface stays type-checked.
    """

    quarters: list[Quarter]
    parameters: dict[str, Any]
    shares_outstanding: Decimal | None
    current_price: Decimal | None
    average_fair_value: Decimal | None
    general_grade_weights: dict[str, Decimal]
    sub_grade_weights: dict[str, dict[str, Decimal]]
    grade_thresholds: dict[str, dict[str, Any]]


@dataclass(slots=True)
class MetricBreakdown:
    """One metric's raw value and its 0-100 score (None when uncomputable)."""

    value: Decimal | None
    score: int | None = None


@dataclass(slots=True)
class SubGradeResult:
    """Sub-grade output. `score` is None when too few metrics were available."""

    score: Decimal | None
    metrics_used: int
    metrics_total: int
    breakdown: dict[str, MetricBreakdown] = field(default_factory=dict)


@dataclass(slots=True)
class GradingResult:
    """Top-level engine output."""

    general: Decimal | None
    sub_grades: dict[str, SubGradeResult]
