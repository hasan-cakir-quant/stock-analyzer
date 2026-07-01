"""Unit tests for the grading engine.

Covers the scorer, sub-grade aggregation (including missing-data
renormalisation), the Incomplete sentinel, general-grade renormalisation,
and an end-to-end fixture with hand-computed expected values.
"""

from __future__ import annotations

from decimal import Decimal

from app.services.grading import GradingInputs, compute_grades, to_payload
from app.services.grading.aggregator import (
    aggregate_general_grade,
    aggregate_sub_grade,
)
from app.services.grading.scorer import score_metric
from app.services.grading.types import SubGradeResult
from app.services.valuations import Quarter


# ---------- helpers --------------------------------------------------------


def _quarters(values: dict) -> list[Quarter]:
    """Build N Quarters where each named field is the same on every quarter."""
    n = next(len(v) for v in values.values())
    return [
        Quarter(
            period=f"P{i}",
            **{
                k: (None if v[i] is None else Decimal(str(v[i])))
                for k, v in values.items()
            },
        )
        for i in range(n)
    ]


# ---------- scorer ---------------------------------------------------------


def test_scorer_higher_better_picks_first_matching_band() -> None:
    threshold = {
        "direction": "higher_better",
        "ranges": [[0.25, 100], [0.10, 50], [None, 0]],
    }
    assert score_metric(Decimal("0.30"), threshold) == 100
    assert score_metric(Decimal("0.10"), threshold) == 50
    assert score_metric(Decimal("0.05"), threshold) == 0


def test_scorer_lower_better_picks_first_matching_band() -> None:
    threshold = {
        "direction": "lower_better",
        "ranges": [[10, 100], [20, 50], [None, 0]],
    }
    assert score_metric(Decimal("8"), threshold) == 100
    assert score_metric(Decimal("15"), threshold) == 50
    assert score_metric(Decimal("25"), threshold) == 0


def test_scorer_returns_none_when_no_band_matches_and_no_catchall() -> None:
    threshold = {"direction": "higher_better", "ranges": [[0.5, 100]]}
    assert score_metric(Decimal("0.1"), threshold) is None


# ---------- sub-grade aggregator -----------------------------------------


_PROFIT_THRESHOLDS = {
    "roe": {"direction": "higher_better", "ranges": [[0.20, 100], [0.10, 50], [None, 0]]},
    "net_margin": {"direction": "higher_better", "ranges": [[0.15, 100], [0.05, 50], [None, 0]]},
}


def test_sub_grade_full_data_weighted_average() -> None:
    """ROE 0.25 → 100, NM 0.05 → 50; equal weights → 75."""
    result = aggregate_sub_grade(
        metric_values={"roe": Decimal("0.25"), "net_margin": Decimal("0.05")},
        metric_weights={"roe": Decimal(50), "net_margin": Decimal(50)},
        thresholds=_PROFIT_THRESHOLDS,
    )
    assert result.metrics_used == 2
    assert result.metrics_total == 2
    assert result.score == Decimal("75")
    assert result.breakdown["roe"].score == 100
    assert result.breakdown["net_margin"].score == 50


def test_sub_grade_renormalises_when_metric_missing() -> None:
    """One metric missing → it drops out, the other carries the sub-grade alone."""
    result = aggregate_sub_grade(
        metric_values={"roe": Decimal("0.25"), "net_margin": None},
        metric_weights={"roe": Decimal(50), "net_margin": Decimal(50)},
        thresholds=_PROFIT_THRESHOLDS,
    )
    assert result.metrics_used == 1
    assert result.metrics_total == 2
    # Renormalised: 100 * 50 / 50 = 100
    assert result.score == Decimal("100")
    assert result.breakdown["net_margin"].score is None


def test_sub_grade_returns_incomplete_when_no_metrics_computable() -> None:
    result = aggregate_sub_grade(
        metric_values={"roe": None, "net_margin": None},
        metric_weights={"roe": Decimal(50), "net_margin": Decimal(50)},
        thresholds=_PROFIT_THRESHOLDS,
    )
    assert result.score is None  # → "Incomplete"
    assert result.metrics_used == 0
    assert result.metrics_total == 2


def test_sub_grade_skips_metrics_without_thresholds() -> None:
    """A metric without a threshold definition is treated as not scoreable."""
    result = aggregate_sub_grade(
        metric_values={"roe": Decimal("0.25"), "mystery_metric": Decimal("42")},
        metric_weights={"roe": Decimal(50), "mystery_metric": Decimal(50)},
        thresholds=_PROFIT_THRESHOLDS,
    )
    assert result.metrics_used == 1
    assert result.score == Decimal("100")


# ---------- general-grade aggregator -------------------------------------


def test_general_grade_weighted_average_of_sub_grades() -> None:
    sub = {
        "profitability": SubGradeResult(score=Decimal("80"), metrics_used=6, metrics_total=6),
        "valuation": SubGradeResult(score=Decimal("60"), metrics_used=6, metrics_total=6),
    }
    weights = {"profitability": Decimal(60), "valuation": Decimal(40)}
    # (80*60 + 60*40) / 100 = (4800 + 2400)/100 = 72
    assert aggregate_general_grade(sub, weights) == Decimal("72")


def test_general_grade_renormalises_when_a_sub_grade_is_incomplete() -> None:
    """Spec: missing sub-grades drop out and the rest renormalise."""
    sub = {
        "profitability": SubGradeResult(score=Decimal("80"), metrics_used=6, metrics_total=6),
        "valuation": SubGradeResult(score=None, metrics_used=0, metrics_total=6),
    }
    weights = {"profitability": Decimal(60), "valuation": Decimal(40)}
    # Valuation drops out → the remaining single sub-grade carries 100% weight.
    assert aggregate_general_grade(sub, weights) == Decimal("80")


def test_general_grade_is_none_when_every_sub_grade_is_incomplete() -> None:
    sub = {
        "profitability": SubGradeResult(score=None, metrics_used=0, metrics_total=6),
    }
    assert aggregate_general_grade(sub, {"profitability": Decimal(100)}) is None


# ---------- end-to-end engine fixture ------------------------------------


def _custom_settings() -> dict:
    """Minimal settings with two metrics in one sub-grade — easy to hand-verify."""
    return {
        "general_grade_weights": {"profitability": Decimal(100)},
        "sub_grade_weights": {
            "profitability": {"roe": Decimal(50), "net_margin": Decimal(50)},
        },
        "grade_thresholds": _PROFIT_THRESHOLDS,
    }


def _profitable_quarters() -> list[Quarter]:
    """4 quarters: NI=25, revenue=500, equity=400 each.
    TTM NI = 100, TTM Revenue = 2000, latest equity = 400.
    ROE = 0.25 → score 100. Net Margin = 0.05 → score 50.
    Profitability = (100*50 + 50*50)/100 = 75. General = 75.
    """
    return _quarters(
        {
            "net_income": [25, 25, 25, 25],
            "revenue": [500, 500, 500, 500],
            "total_equity": [400, 400, 400, 400],
        }
    )


def test_engine_end_to_end_matches_hand_computed_scores() -> None:
    settings = _custom_settings()
    inputs = GradingInputs(
        quarters=_profitable_quarters(),
        parameters={},
        shares_outstanding=None,
        current_price=None,
        average_fair_value=None,
        general_grade_weights=settings["general_grade_weights"],
        sub_grade_weights=settings["sub_grade_weights"],
        grade_thresholds=settings["grade_thresholds"],
    )
    result = compute_grades(inputs)
    assert result.general == Decimal("75")

    profitability = result.sub_grades["profitability"]
    assert profitability.score == Decimal("75")
    assert profitability.metrics_used == 2
    assert profitability.breakdown["roe"].value == Decimal("0.25")
    assert profitability.breakdown["roe"].score == 100
    assert profitability.breakdown["net_margin"].value == Decimal("0.05")
    assert profitability.breakdown["net_margin"].score == 50


def test_engine_end_to_end_renormalises_when_one_metric_missing() -> None:
    """Drop revenue so net_margin can't be computed; ROE still scores."""
    quarters = _quarters(
        {
            "net_income": [25, 25, 25, 25],
            "revenue": [None, None, None, None],
            "total_equity": [400, 400, 400, 400],
        }
    )
    settings = _custom_settings()
    inputs = GradingInputs(
        quarters=quarters,
        parameters={},
        shares_outstanding=None,
        current_price=None,
        average_fair_value=None,
        general_grade_weights=settings["general_grade_weights"],
        sub_grade_weights=settings["sub_grade_weights"],
        grade_thresholds=settings["grade_thresholds"],
    )
    result = compute_grades(inputs)
    assert result.sub_grades["profitability"].score == Decimal("100")
    assert result.sub_grades["profitability"].metrics_used == 1
    assert result.sub_grades["profitability"].breakdown["net_margin"].score is None
    assert result.general == Decimal("100")


def test_engine_end_to_end_payload_shape_matches_requirements() -> None:
    settings = _custom_settings()
    inputs = GradingInputs(
        quarters=_profitable_quarters(),
        parameters={},
        shares_outstanding=None,
        current_price=None,
        average_fair_value=None,
        general_grade_weights=settings["general_grade_weights"],
        sub_grade_weights=settings["sub_grade_weights"],
        grade_thresholds=settings["grade_thresholds"],
    )
    payload = to_payload(compute_grades(inputs))
    assert payload["general"] == 75.0
    profit = payload["sub_grades"]["profitability"]
    assert profit["score"] == 75.0
    assert profit["metrics_used"] == 2
    assert profit["metrics_total"] == 2
    assert profit["breakdown"]["roe"] == {"value": 0.25, "score": 100}
    assert profit["breakdown"]["net_margin"] == {"value": 0.05, "score": 50}


def test_engine_end_to_end_general_renorm_with_missing_sub_grade() -> None:
    """Two sub-grades configured; only one has computable metrics → general
    follows the surviving one (renormalised)."""
    settings = {
        "general_grade_weights": {
            "profitability": Decimal(50),
            "valuation": Decimal(50),
        },
        "sub_grade_weights": {
            "profitability": {"roe": Decimal(100)},
            "valuation": {"pe": Decimal(100)},
        },
        "grade_thresholds": {
            "roe": _PROFIT_THRESHOLDS["roe"],
            "pe": {"direction": "lower_better", "ranges": [[15, 100], [25, 50], [None, 0]]},
        },
    }
    quarters = _quarters(
        {
            "net_income": [25, 25, 25, 25],
            "total_equity": [100, 100, 100, 100],
            # No EPS data → P/E uncomputable → valuation Incomplete.
        }
    )
    inputs = GradingInputs(
        quarters=quarters,
        parameters={},
        shares_outstanding=None,
        current_price=Decimal("100"),
        average_fair_value=None,
        general_grade_weights=settings["general_grade_weights"],
        sub_grade_weights=settings["sub_grade_weights"],
        grade_thresholds=settings["grade_thresholds"],
    )
    result = compute_grades(inputs)
    # ROE = 100/100 = 1.0 → score 100. Profitability = 100. General renormalises to 100.
    assert result.sub_grades["valuation"].score is None
    assert result.sub_grades["profitability"].score == Decimal("100")
    assert result.general == Decimal("100")
