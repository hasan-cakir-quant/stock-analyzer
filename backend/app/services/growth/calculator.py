"""Growth calculator — CAGRs and trend deltas across 1Y / 3Y / 5Y / 10Y horizons.

Conventions:
  * **Flow** metrics (income statement, cash-flow) are aggregated as TTM
    sums; an N-year CAGR compares the latest TTM to the TTM ending N
    years ago. Requires ≥ 4*N + 4 quarters of contiguous data.
  * **Stock** metrics (balance-sheet items) take the value at the end of
    the relevant quarter. An N-year CAGR compares the latest quarter to
    the quarter N years (4*N quarters) before. Requires ≥ 4*N + 1.
  * **Trend** metrics (margins, ROE) are ratios — the spec asks for
    "trend", not "growth", so we report the *delta* (in decimal form,
    e.g. 0.05 = +5 percentage points), not a CAGR.
  * Per-share metrics with constant share count reduce to the underlying
    flow/stock — we report Book Value/Share growth as `total_equity`
    growth and Dividend/Share growth as TTM dividends growth.
"""

from __future__ import annotations

from decimal import Decimal

from app.services.growth.types import HORIZONS, GrowthInputs, GrowthResult, MetricHorizons
from app.services.valuations.types import Quarter

TTM_QUARTERS = 4


def _cagr(start: Decimal, end: Decimal, years: int) -> Decimal | None:
    if start <= 0 or end <= 0 or years <= 0:
        return None
    growth = (float(end) / float(start)) ** (1.0 / years) - 1.0
    return Decimal(str(growth))


def _ttm_ending(
    quarters: list[Quarter], field_name: str, years_back: int
) -> Decimal | None:
    """TTM sum of `field_name` for the year ending `years_back` years before the latest."""
    end = len(quarters) - years_back * TTM_QUARTERS
    start = end - TTM_QUARTERS
    if start < 0:
        return None
    values = [getattr(q, field_name) for q in quarters[start:end]]
    if any(v is None for v in values):
        return None
    return sum(values, start=Decimal(0))


def _value_at(
    quarters: list[Quarter], field_name: str, years_back: int
) -> Decimal | None:
    """Point-in-time value at the quarter `years_back` years before the latest."""
    idx = len(quarters) - 1 - years_back * TTM_QUARTERS
    if idx < 0:
        return None
    return getattr(quarters[idx], field_name)


def _flow_growth(
    quarters: list[Quarter], field_name: str, years: int, *, use_abs: bool = False
) -> Decimal | None:
    start = _ttm_ending(quarters, field_name, years)
    end = _ttm_ending(quarters, field_name, 0)
    if start is None or end is None:
        return None
    if use_abs:
        # Cash-flow line items (e.g. dividends_paid) are conventionally
        # negative; growth-of-magnitude is what the user actually wants.
        start, end = abs(start), abs(end)
    return _cagr(start, end, years)


def _stock_growth(
    quarters: list[Quarter], field_name: str, years: int
) -> Decimal | None:
    start = _value_at(quarters, field_name, years)
    end = _value_at(quarters, field_name, 0)
    if start is None or end is None:
        return None
    return _cagr(start, end, years)


def _ratio_at(
    quarters: list[Quarter], num_field: str, denom_field: str, years_back: int
) -> Decimal | None:
    num = _ttm_ending(quarters, num_field, years_back)
    denom = _ttm_ending(quarters, denom_field, years_back)
    if num is None or denom is None or denom == 0:
        return None
    return num / denom


def _margin_trend(
    quarters: list[Quarter], num_field: str, denom_field: str, years: int
) -> Decimal | None:
    end = _ratio_at(quarters, num_field, denom_field, 0)
    start = _ratio_at(quarters, num_field, denom_field, years)
    if end is None or start is None:
        return None
    return end - start


def _roe_at(quarters: list[Quarter], years_back: int) -> Decimal | None:
    ni = _ttm_ending(quarters, "net_income", years_back)
    equity = _value_at(quarters, "total_equity", years_back)
    if ni is None or equity is None or equity <= 0:
        return None
    return ni / equity


def _roe_trend(quarters: list[Quarter], years: int) -> Decimal | None:
    end = _roe_at(quarters, 0)
    start = _roe_at(quarters, years)
    if end is None or start is None:
        return None
    return end - start


# Each tuple: (metric_id, source_field, use_abs?). use_abs is True for
# cash-flow items conventionally reported as negative outflows.
_FLOW_METRICS: tuple[tuple[str, str, bool], ...] = (
    ("revenue", "revenue", False),
    ("operating_income", "operating_income", False),
    ("net_income", "net_income", False),
    ("ebitda", "ebitda", False),
    ("eps_diluted", "eps_diluted", False),
    ("free_cash_flow", "free_cash_flow", False),
    ("operating_cash_flow", "operating_cash_flow", False),
    # Per-share growth with constant shares reduces to the underlying flow.
    ("dividend_per_share", "dividends_paid", True),
)


def compute_growth(inputs: GrowthInputs) -> GrowthResult:
    metrics: dict[str, MetricHorizons] = {}

    for metric_id, source_field, use_abs in _FLOW_METRICS:
        metrics[metric_id] = MetricHorizons(
            values={
                y: _flow_growth(inputs.quarters, source_field, y, use_abs=use_abs)
                for y in HORIZONS
            }
        )

    # Book Value / Share — report total_equity growth (constant shares simplification).
    metrics["book_value_per_share"] = MetricHorizons(
        values={y: _stock_growth(inputs.quarters, "total_equity", y) for y in HORIZONS}
    )

    # Total equity — same source as book_value_per_share, but surfaced
    # under its own key so frontends that show the level (not per-share)
    # can read it directly without re-deriving.
    metrics["total_equity"] = MetricHorizons(
        values={y: _stock_growth(inputs.quarters, "total_equity", y) for y in HORIZONS}
    )

    # Trend metrics — delta in the ratio over the horizon (decimal points).
    metrics["gross_margin_trend"] = MetricHorizons(
        values={y: _margin_trend(inputs.quarters, "gross_profit", "revenue", y) for y in HORIZONS}
    )
    metrics["operating_margin_trend"] = MetricHorizons(
        values={
            y: _margin_trend(inputs.quarters, "operating_income", "revenue", y) for y in HORIZONS
        }
    )
    metrics["roe_trend"] = MetricHorizons(
        values={y: _roe_trend(inputs.quarters, y) for y in HORIZONS}
    )

    return GrowthResult(metrics=metrics)
