"""Internal helpers shared by valuation models.

Everything here returns either a Decimal or None — never raises on missing
data. Callers decide whether the absence is fatal for their model.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from statistics import median
from typing import Any

from app.services.valuations.types import Quarter

# How many quarters make up a trailing-twelve-months sum.
TTM_QUARTERS = 4
# Minimum quarters of history we need before we'll compute a CAGR.
MIN_GROWTH_QUARTERS = 8
# Most recent N years of YoY growth to consider for the weighted CAGR.
# Older history is dropped so a long backtrack doesn't dilute the
# weighted average. With N rates we need N+1 TTM points.
MAX_WEIGHTED_CAGR_YEARS = 5

# Implied-ERP guard rails (Damodaran-style). If the Gordon-growth
# computation lands outside this band we treat the inputs as
# unreliable and fall back to ERP_FALLBACK.
ERP_FLOOR = Decimal("0.03")
ERP_CEILING = Decimal("0.08")
ERP_FALLBACK = Decimal("0.05")
ERP_FALLBACK_REASON = "Insufficient data — used default ERP 5%"


def _to_decimal(value: Any) -> Decimal | None:
    """Coerce a parameter (str | int | float | Decimal | None) to Decimal."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def get_param(params: dict[str, Any], key: str) -> Decimal | None:
    return _to_decimal(params.get(key))


def get_int_param(params: dict[str, Any], key: str) -> int | None:
    raw = params.get(key)
    return int(raw) if raw is not None else None


def latest(quarters: list[Quarter], field: str) -> Decimal | None:
    """Most recent non-null value for `field` (scanning from newest)."""
    for q in reversed(quarters):
        value = getattr(q, field)
        if value is not None:
            return value
    return None


def latest_shares_outstanding(quarters: list[Quarter]) -> Decimal | None:
    """Latest non-null `shares_outstanding_diluted` reported on the income statement.

    Thin wrapper around `latest` that encodes a naming convention:
    valuations should prefer the diluted share count off the most
    recent quarterly statement (it's the per-share basis used for
    diluted EPS) over stock metadata, which is often stale.
    """
    return latest(quarters, "shares_outstanding_diluted")


def ttm_sum(quarters: list[Quarter], field: str) -> Decimal | None:
    """Sum the last 4 reported values for `field`. Needs all 4 to be non-null."""
    if len(quarters) < TTM_QUARTERS:
        return None
    window = quarters[-TTM_QUARTERS:]
    values = [getattr(q, field) for q in window]
    if any(v is None for v in values):
        return None
    return sum(values, start=Decimal(0))


def annualised_growth_rate(values: list[Decimal]) -> Decimal | None:
    """CAGR over a sequence of TTM-style values, returned as a decimal (0.05 = 5%).

    `values` is ordered oldest→newest and assumed to be one-year apart per step.
    """
    if len(values) < 2:
        return None
    start, end = values[0], values[-1]
    if start <= 0 or end <= 0:
        return None
    years = len(values) - 1
    # Decimal doesn't do fractional exponents — drop to float for the root.
    growth = (float(end) / float(start)) ** (1.0 / years) - 1.0
    return Decimal(str(growth))


def rolling_ttm_series(quarters: list[Quarter], field: str) -> list[Decimal]:
    """Sequence of trailing-twelve-month sums, stepping one year (4 quarters) at a time.

    Returns the empty list if there isn't even a full TTM window.
    """
    series: list[Decimal] = []
    if len(quarters) < TTM_QUARTERS:
        return series
    # Walk newest-first, take TTM windows spaced by 4 quarters apart.
    for end in range(len(quarters), TTM_QUARTERS - 1, -TTM_QUARTERS):
        window = quarters[end - TTM_QUARTERS : end]
        values = [getattr(q, field) for q in window]
        if any(v is None for v in values):
            continue
        series.append(sum(values, start=Decimal(0)))
    series.reverse()  # oldest → newest, matches what `annualised_growth_rate` expects
    return series


@dataclass(slots=True, frozen=True)
class TTMWindow:
    """One trailing-twelve-month window — total + the 4 quarters that compose it.

    Used by callers that want to surface the breakdown of a CAGR calculation,
    not just the final number.
    """

    period_start: str  # oldest quarter in the window, e.g. "2022-Q1"
    period_end: str  # newest quarter in the window, e.g. "2022-Q4"
    quarter_values: list[tuple[str, Decimal]]  # [("2022-Q1", Decimal(...)), ...]
    total: Decimal


def rolling_ttm_windows(quarters: list[Quarter], field: str) -> list[TTMWindow]:
    """Like `rolling_ttm_series` but returns the per-quarter values too.

    Result is ordered oldest→newest. Windows containing any None values for
    `field` are skipped, matching `rolling_ttm_series`.
    """
    windows: list[TTMWindow] = []
    if len(quarters) < TTM_QUARTERS:
        return windows
    for end in range(len(quarters), TTM_QUARTERS - 1, -TTM_QUARTERS):
        window = quarters[end - TTM_QUARTERS : end]
        values = [getattr(q, field) for q in window]
        if any(v is None for v in values):
            continue
        windows.append(
            TTMWindow(
                period_start=window[0].period,
                period_end=window[-1].period,
                quarter_values=[(q.period, v) for q, v in zip(window, values)],
                total=sum(values, start=Decimal(0)),
            )
        )
    windows.reverse()
    return windows


def historical_cagr(quarters: list[Quarter], field: str) -> Decimal | None:
    """CAGR of a TTM series for `field`. None if not enough history."""
    series = rolling_ttm_series(quarters, field)
    if len(series) < MIN_GROWTH_QUARTERS // TTM_QUARTERS:
        return None
    return annualised_growth_rate(series)


def weighted_cagr(quarters: list[Quarter], field: str) -> Decimal | None:
    """Linearly-weighted average of year-over-year TTM growth rates.

    Computes one YoY rate per consecutive TTM-point pair from at most
    the newest `MAX_WEIGHTED_CAGR_YEARS + 1` TTM points (so up to N
    YoY rates from the most recent N years), then takes a weighted
    mean where the most recent transition gets the highest weight.
    Weights are 1, 2, …, M — newest last — so with 5 YoY rates the
    newest is weighted 5× the oldest.

    Drop-in replacement for `historical_cagr`: same arguments, same
    None-when-insufficient guard. Returns None if any prior TTM is
    non-positive (YoY is undefined off a non-positive base).
    """
    series = rolling_ttm_series(quarters, field)
    if len(series) < MIN_GROWTH_QUARTERS // TTM_QUARTERS:
        return None
    # Trim to the most recent (N + 1) TTM points so the weighted
    # average reflects recent trend, not the entire reportable history.
    series = series[-(MAX_WEIGHTED_CAGR_YEARS + 1) :]
    if len(series) < 2:
        return None  # need at least one YoY transition

    weighted_sum = Decimal(0)
    weight_sum = Decimal(0)
    for i in range(1, len(series)):
        prior, current = series[i - 1], series[i]
        if prior <= 0:
            return None
        rate = (current - prior) / prior
        weight = Decimal(i)  # 1, 2, …, len(series)-1 — newest carries the highest weight
        weighted_sum += weight * rate
        weight_sum += weight
    return weighted_sum / weight_sum


def estimate_equity_risk_premium(
    *,
    quarters: list[Quarter],
    risk_free_rate: Decimal,
    earnings_field: str = "eps_diluted",
    price_field: str = "closing_price",
) -> tuple[Decimal, str]:
    """Implied equity risk premium via the Damodaran Gordon-growth approach.

    Formula::

        implied ERP = (TTM earnings yield) + earnings growth − risk-free rate

    The earnings yield is the trailing-twelve-month sum of `earnings_field`
    divided by the latest non-null `price_field` (so for the per-share
    pairing `eps_diluted` ÷ `closing_price`). Growth is the CAGR of the
    rolling-TTM earnings series.

    The result must land in [`ERP_FLOOR`, `ERP_CEILING`] (3%–8%);
    anything outside, or any failure in the chain (missing data,
    non-positive yields, division by zero), falls back to
    `ERP_FALLBACK` (5%) with `ERP_FALLBACK_REASON`.

    Returns ``(erp, reason)`` — the reason is a human-readable string
    intended for display in the popover worksheet.
    """
    try:
        ttm_earnings = ttm_sum(quarters, earnings_field)
        if ttm_earnings is None or ttm_earnings <= 0:
            return ERP_FALLBACK, ERP_FALLBACK_REASON
        current_price = latest(quarters, price_field)
        if current_price is None or current_price <= 0:
            return ERP_FALLBACK, ERP_FALLBACK_REASON

        earnings_yield = ttm_earnings / current_price
        if earnings_yield <= 0:
            return ERP_FALLBACK, ERP_FALLBACK_REASON

        series = rolling_ttm_series(quarters, earnings_field)
        if len(series) < MIN_GROWTH_QUARTERS // TTM_QUARTERS:
            return ERP_FALLBACK, ERP_FALLBACK_REASON
        growth = annualised_growth_rate(series)
        if growth is None:
            return ERP_FALLBACK, ERP_FALLBACK_REASON

        implied = earnings_yield + growth - risk_free_rate
        if implied < ERP_FLOOR or implied > ERP_CEILING:
            return ERP_FALLBACK, ERP_FALLBACK_REASON
        return implied, "Computed from market earnings yield + growth (Gordon)"
    except (ZeroDivisionError, ArithmeticError):
        return ERP_FALLBACK, ERP_FALLBACK_REASON


def estimate_discount_rate(
    *,
    risk_free_rate: Decimal,
    quarters: list[Quarter],
    beta: Decimal = Decimal(1),
    earnings_field: str = "eps_diluted",
    price_field: str = "closing_price",
    erp: Decimal | None = None,
) -> tuple[Decimal, Decimal, str]:
    """CAPM cost of equity: ``r = rf + β × ERP``.

    If `erp` is None, derives one via `estimate_equity_risk_premium`
    using the supplied quarters. If a value is supplied (typically
    because the user manually entered ``equity_risk_premium`` in the
    Parameter Panel), that value is used as-is.

    Returns ``(discount_rate, erp_used, erp_reason)`` so callers can
    surface every component of the CAPM derivation in a worksheet.
    """
    if erp is None:
        erp_value, erp_reason = estimate_equity_risk_premium(
            quarters=quarters,
            risk_free_rate=risk_free_rate,
            earnings_field=earnings_field,
            price_field=price_field,
        )
    else:
        erp_value = erp
        erp_reason = "User-supplied"

    discount = risk_free_rate + beta * erp_value
    return discount, erp_value, erp_reason


def compute_wacc(
    *,
    cost_of_equity: Decimal,
    pretax_cost_of_debt: Decimal,
    tax_rate: Decimal,
    market_cap: Decimal,
    total_debt: Decimal,
) -> Decimal:
    """Weighted-average cost of capital: ``w_e × r_e + w_d × r_d × (1 − τ)``.

    Blends after-tax cost of debt with cost of equity by market-value
    weights. Falls back to `cost_of_equity` if the total capital base is
    non-positive (debt-free *and* equity-less is degenerate — shouldn't
    happen, but guards the division).
    """
    after_tax_cost_of_debt = pretax_cost_of_debt * (Decimal(1) - tax_rate)
    total_capital = market_cap + total_debt
    if total_capital <= 0:
        return cost_of_equity
    weight_equity = market_cap / total_capital
    weight_debt = total_debt / total_capital
    return weight_equity * cost_of_equity + weight_debt * after_tax_cost_of_debt


def median_decimal(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    # statistics.median handles Decimals, but returns the average of the two
    # middles when len is even — wrapped here for type clarity.
    return Decimal(str(median(values)))
