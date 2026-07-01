"""Metric calculator — raw values for every metric across the seven sub-grades.

Each metric is a small function that returns `Decimal | None`. None means
"can't compute given the data we have"; the aggregator handles missing
values by renormalising weights.

All functions read from `GradingInputs` so the engine can route data
without each metric needing a different signature.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Callable

from app.services.grading.types import GradingInputs
from app.services.valuations._helpers import (
    historical_cagr,
    latest,
    rolling_ttm_series,
    ttm_sum,
)

DAYS_PER_YEAR = Decimal(365)


# ---------------------------------------------------------------------------
# Profitability
# ---------------------------------------------------------------------------


def roe(g: GradingInputs) -> Decimal | None:
    ni = ttm_sum(g.quarters, "net_income")
    eq = latest(g.quarters, "total_equity")
    if ni is None or eq is None or eq <= 0:
        return None
    return ni / eq


def roa(g: GradingInputs) -> Decimal | None:
    ni = ttm_sum(g.quarters, "net_income")
    assets = latest(g.quarters, "total_assets")
    if ni is None or assets is None or assets <= 0:
        return None
    return ni / assets


def roic(g: GradingInputs) -> Decimal | None:
    """Approximation: TTM net income / (equity + total debt)."""
    ni = ttm_sum(g.quarters, "net_income")
    eq = latest(g.quarters, "total_equity")
    ltd = latest(g.quarters, "long_term_debt") or Decimal(0)
    std = latest(g.quarters, "short_term_debt") or Decimal(0)
    if ni is None or eq is None:
        return None
    invested = eq + ltd + std
    if invested <= 0:
        return None
    return ni / invested


def net_margin(g: GradingInputs) -> Decimal | None:
    ni = ttm_sum(g.quarters, "net_income")
    rev = ttm_sum(g.quarters, "revenue")
    if ni is None or rev is None or rev <= 0:
        return None
    return ni / rev


def gross_margin(g: GradingInputs) -> Decimal | None:
    gp = ttm_sum(g.quarters, "gross_profit")
    rev = ttm_sum(g.quarters, "revenue")
    if gp is None or rev is None or rev <= 0:
        return None
    return gp / rev


def operating_margin(g: GradingInputs) -> Decimal | None:
    op = ttm_sum(g.quarters, "operating_income")
    rev = ttm_sum(g.quarters, "revenue")
    if op is None or rev is None or rev <= 0:
        return None
    return op / rev


# ---------------------------------------------------------------------------
# Financial Strength
# ---------------------------------------------------------------------------


def debt_to_equity(g: GradingInputs) -> Decimal | None:
    eq = latest(g.quarters, "total_equity")
    ltd = latest(g.quarters, "long_term_debt")
    std = latest(g.quarters, "short_term_debt")
    if eq is None or eq <= 0 or (ltd is None and std is None):
        return None
    debt = (ltd or Decimal(0)) + (std or Decimal(0))
    return debt / eq


def current_ratio(g: GradingInputs) -> Decimal | None:
    ca = latest(g.quarters, "total_current_assets")
    cl = latest(g.quarters, "total_current_liabilities")
    if ca is None or cl is None or cl <= 0:
        return None
    return ca / cl


def quick_ratio(g: GradingInputs) -> Decimal | None:
    cash = latest(g.quarters, "cash_and_equivalents") or Decimal(0)
    sti = latest(g.quarters, "short_term_investments") or Decimal(0)
    rec = latest(g.quarters, "receivables") or Decimal(0)
    cl = latest(g.quarters, "total_current_liabilities")
    if cl is None or cl <= 0:
        return None
    return (cash + sti + rec) / cl


def interest_coverage(g: GradingInputs) -> Decimal | None:
    op = ttm_sum(g.quarters, "operating_income")
    interest = ttm_sum(g.quarters, "interest_expense")
    if op is None or interest is None:
        return None
    interest = abs(interest)  # statements often report a negative outflow
    if interest == 0:
        return None
    return op / interest


def debt_to_ebitda(g: GradingInputs) -> Decimal | None:
    ltd = latest(g.quarters, "long_term_debt")
    std = latest(g.quarters, "short_term_debt")
    ebitda = ttm_sum(g.quarters, "ebitda")
    if ebitda is None or ebitda <= 0 or (ltd is None and std is None):
        return None
    debt = (ltd or Decimal(0)) + (std or Decimal(0))
    return debt / ebitda


# ---------------------------------------------------------------------------
# Valuation
# ---------------------------------------------------------------------------


def pe(g: GradingInputs) -> Decimal | None:
    eps = ttm_sum(g.quarters, "eps_diluted")
    if g.current_price is None or eps is None or eps <= 0:
        return None
    return g.current_price / eps


def pb(g: GradingInputs) -> Decimal | None:
    eq = latest(g.quarters, "total_equity")
    if g.current_price is None or g.shares_outstanding is None or eq is None or eq <= 0:
        return None
    if g.shares_outstanding <= 0:
        return None
    bvps = eq / g.shares_outstanding
    if bvps <= 0:
        return None
    return g.current_price / bvps


def ps(g: GradingInputs) -> Decimal | None:
    rev = ttm_sum(g.quarters, "revenue")
    if g.current_price is None or g.shares_outstanding is None or rev is None or rev <= 0:
        return None
    if g.shares_outstanding <= 0:
        return None
    return (g.current_price * g.shares_outstanding) / rev


def ev_ebitda(g: GradingInputs) -> Decimal | None:
    ebitda = ttm_sum(g.quarters, "ebitda")
    if g.current_price is None or g.shares_outstanding is None or ebitda is None:
        return None
    if g.shares_outstanding <= 0 or ebitda <= 0:
        return None
    market_cap = g.current_price * g.shares_outstanding
    ltd = latest(g.quarters, "long_term_debt") or Decimal(0)
    std = latest(g.quarters, "short_term_debt") or Decimal(0)
    cash = latest(g.quarters, "cash_and_equivalents") or Decimal(0)
    enterprise_value = market_cap + ltd + std - cash
    return enterprise_value / ebitda


def peg(g: GradingInputs) -> Decimal | None:
    pe_value = pe(g)
    eps_cagr = historical_cagr(g.quarters, "eps_diluted")
    if pe_value is None or eps_cagr is None:
        return None
    growth_pct = eps_cagr * Decimal(100)
    if growth_pct <= 0:
        return None
    return pe_value / growth_pct


def price_vs_fair_value(g: GradingInputs) -> Decimal | None:
    """Current price as a fraction of the average fair value (1.0 = fairly priced)."""
    if g.current_price is None or g.average_fair_value is None or g.average_fair_value <= 0:
        return None
    return g.current_price / g.average_fair_value


# ---------------------------------------------------------------------------
# Growth
# ---------------------------------------------------------------------------


def revenue_growth(g: GradingInputs) -> Decimal | None:
    return historical_cagr(g.quarters, "revenue")


def eps_growth(g: GradingInputs) -> Decimal | None:
    return historical_cagr(g.quarters, "eps_diluted")


def fcf_growth(g: GradingInputs) -> Decimal | None:
    return historical_cagr(g.quarters, "free_cash_flow")


def book_value_growth(g: GradingInputs) -> Decimal | None:
    """CAGR of total_equity sampled at one-year intervals."""
    if len(g.quarters) < 8:
        return None
    samples = g.quarters[::4]
    values = [q.total_equity for q in samples if q.total_equity is not None]
    if len(values) < 2:
        return None
    start, end = values[0], values[-1]
    if start <= 0 or end <= 0:
        return None
    years = len(values) - 1
    growth = (float(end) / float(start)) ** (1.0 / years) - 1.0
    return Decimal(str(growth))


# ---------------------------------------------------------------------------
# Efficiency
# ---------------------------------------------------------------------------


def asset_turnover(g: GradingInputs) -> Decimal | None:
    rev = ttm_sum(g.quarters, "revenue")
    assets = latest(g.quarters, "total_assets")
    if rev is None or assets is None or assets <= 0:
        return None
    return rev / assets


def inventory_turnover(g: GradingInputs) -> Decimal | None:
    cogs = ttm_sum(g.quarters, "cogs")
    inv = latest(g.quarters, "inventory")
    if cogs is None or inv is None or inv <= 0:
        return None
    return cogs / inv


def cash_conversion_cycle(g: GradingInputs) -> Decimal | None:
    """DIO + DSO. We don't track payables yet, so DPO is omitted."""
    cogs = ttm_sum(g.quarters, "cogs")
    rev = ttm_sum(g.quarters, "revenue")
    inv = latest(g.quarters, "inventory")
    rec = latest(g.quarters, "receivables")
    if cogs is None or rev is None or inv is None or rec is None:
        return None
    if cogs <= 0 or rev <= 0:
        return None
    dio = inv * DAYS_PER_YEAR / cogs
    dso = rec * DAYS_PER_YEAR / rev
    return dio + dso


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------


def beta(g: GradingInputs) -> Decimal | None:
    raw = g.parameters.get("beta")
    return Decimal(str(raw)) if raw is not None else None


def altman_z_score(g: GradingInputs) -> Decimal | None:
    """Standard 5-factor Z-score, with total_equity as a stand-in for retained
    earnings since we don't track that line item separately yet.
    """
    assets = latest(g.quarters, "total_assets")
    ca = latest(g.quarters, "total_current_assets")
    cl = latest(g.quarters, "total_current_liabilities")
    eq = latest(g.quarters, "total_equity")
    op = ttm_sum(g.quarters, "operating_income")
    rev = ttm_sum(g.quarters, "revenue")
    liabilities_ltd = latest(g.quarters, "long_term_debt") or Decimal(0)
    liabilities_std = latest(g.quarters, "short_term_debt") or Decimal(0)
    total_liabilities = liabilities_ltd + liabilities_std + (cl or Decimal(0))

    if assets is None or assets <= 0 or total_liabilities <= 0:
        return None
    if ca is None or cl is None or eq is None or op is None or rev is None:
        return None
    if g.current_price is None or g.shares_outstanding is None or g.shares_outstanding <= 0:
        return None

    a = (ca - cl) / assets
    b = eq / assets
    c = op / assets
    d = (g.current_price * g.shares_outstanding) / total_liabilities
    e = rev / assets
    return Decimal("1.2") * a + Decimal("1.4") * b + Decimal("3.3") * c + Decimal("0.6") * d + e


def piotroski_f_score(g: GradingInputs) -> Decimal | None:
    """Nine-point F-score: latest TTM compared to the trailing year before it."""
    if len(g.quarters) < 8:
        return None

    now = g.quarters[-4:]
    prior = g.quarters[-8:-4]

    def _ttm(window: list, field: str) -> Decimal | None:
        values = [getattr(q, field) for q in window]
        if any(v is None for v in values):
            return None
        return sum(values, start=Decimal(0))

    ni_now = _ttm(now, "net_income")
    ocf_now = _ttm(now, "operating_cash_flow")
    rev_now = _ttm(now, "revenue")
    cogs_now = _ttm(now, "cogs")

    ni_prior = _ttm(prior, "net_income")
    rev_prior = _ttm(prior, "revenue")
    cogs_prior = _ttm(prior, "cogs")

    assets_now = latest(now, "total_assets")
    assets_prior = latest(prior, "total_assets")
    ltd_now = latest(now, "long_term_debt")
    ltd_prior = latest(prior, "long_term_debt")
    ca_now = latest(now, "total_current_assets")
    cl_now = latest(now, "total_current_liabilities")
    ca_prior = latest(prior, "total_current_assets")
    cl_prior = latest(prior, "total_current_liabilities")
    shares_now = latest(now, "shares_outstanding_diluted")
    shares_prior = latest(prior, "shares_outstanding_diluted")

    score = 0
    # 1. Positive net income
    if ni_now is not None and ni_now > 0:
        score += 1
    # 2. Positive operating cash flow
    if ocf_now is not None and ocf_now > 0:
        score += 1
    # 3. ROA improving
    if (
        ni_now is not None
        and ni_prior is not None
        and assets_now
        and assets_prior
        and (ni_now / assets_now) > (ni_prior / assets_prior)
    ):
        score += 1
    # 4. OCF > NI (accruals quality)
    if ocf_now is not None and ni_now is not None and ocf_now > ni_now:
        score += 1
    # 5. LT debt down
    if ltd_now is not None and ltd_prior is not None and ltd_now < ltd_prior:
        score += 1
    # 6. Current ratio improving
    if (
        ca_now is not None
        and cl_now
        and ca_prior is not None
        and cl_prior
        and (ca_now / cl_now) > (ca_prior / cl_prior)
    ):
        score += 1
    # 7. Shares not increased
    if shares_now is not None and shares_prior is not None and shares_now <= shares_prior:
        score += 1
    # 8. Gross margin improving
    if (
        rev_now
        and cogs_now is not None
        and rev_prior
        and cogs_prior is not None
        and ((rev_now - cogs_now) / rev_now) > ((rev_prior - cogs_prior) / rev_prior)
    ):
        score += 1
    # 9. Asset turnover improving
    if (
        rev_now is not None
        and assets_now
        and rev_prior is not None
        and assets_prior
        and (rev_now / assets_now) > (rev_prior / assets_prior)
    ):
        score += 1

    return Decimal(score)


def debt_levels(g: GradingInputs) -> Decimal | None:
    """Total debt / total assets — proxy for leverage."""
    assets = latest(g.quarters, "total_assets")
    ltd = latest(g.quarters, "long_term_debt")
    std = latest(g.quarters, "short_term_debt")
    if assets is None or assets <= 0 or (ltd is None and std is None):
        return None
    debt = (ltd or Decimal(0)) + (std or Decimal(0))
    return debt / assets


# ---------------------------------------------------------------------------
# Dividend
# ---------------------------------------------------------------------------


def _ttm_dividends_abs(g: GradingInputs) -> Decimal | None:
    raw = ttm_sum(g.quarters, "dividends_paid")
    return abs(raw) if raw is not None else None


def dividend_yield(g: GradingInputs) -> Decimal | None:
    div = _ttm_dividends_abs(g)
    if (
        div is None
        or div == 0
        or g.shares_outstanding is None
        or g.shares_outstanding <= 0
        or g.current_price is None
        or g.current_price <= 0
    ):
        return None
    dps = div / g.shares_outstanding
    return dps / g.current_price


def payout_ratio(g: GradingInputs) -> Decimal | None:
    div = _ttm_dividends_abs(g)
    ni = ttm_sum(g.quarters, "net_income")
    if div is None or ni is None or ni <= 0:
        return None
    return div / ni


def dividend_growth_rate(g: GradingInputs) -> Decimal | None:
    series = rolling_ttm_series(g.quarters, "dividends_paid")
    if len(series) < 2:
        return None
    series = [abs(v) for v in series]
    if any(v <= 0 for v in series):
        return None
    years = len(series) - 1
    growth = (float(series[-1]) / float(series[0])) ** (1.0 / years) - 1.0
    return Decimal(str(growth))


def consecutive_growth_years(g: GradingInputs) -> Decimal | None:
    series = rolling_ttm_series(g.quarters, "dividends_paid")
    if len(series) < 2:
        return None
    series = [abs(v) for v in series]
    count = 0
    for i in range(len(series) - 1, 0, -1):
        if series[i] > series[i - 1]:
            count += 1
        else:
            break
    return Decimal(count)


# ---------------------------------------------------------------------------
# Registry — sub-grade name -> {metric_name: callable}
# ---------------------------------------------------------------------------


SUB_GRADE_METRICS: dict[str, dict[str, Callable[[GradingInputs], Decimal | None]]] = {
    "profitability": {
        "roe": roe,
        "roa": roa,
        "roic": roic,
        "net_margin": net_margin,
        "gross_margin": gross_margin,
        "operating_margin": operating_margin,
    },
    "financial_strength": {
        "debt_to_equity": debt_to_equity,
        "current_ratio": current_ratio,
        "quick_ratio": quick_ratio,
        "interest_coverage": interest_coverage,
        "debt_to_ebitda": debt_to_ebitda,
    },
    "valuation": {
        "pe": pe,
        "pb": pb,
        "ps": ps,
        "ev_ebitda": ev_ebitda,
        "peg": peg,
        # price_vs_fair_value intentionally omitted — it's the only valuation
        # metric that depends on the parameter set (via the average fair value),
        # which made grades shift across compare-mode template columns. Migration
        # 0009 pro-rata-rescales the remaining weights to 100 and drops the
        # threshold entry so the metric never gets surfaced or scored.
    },
    "growth": {
        "revenue_growth": revenue_growth,
        "eps_growth": eps_growth,
        "fcf_growth": fcf_growth,
        "book_value_growth": book_value_growth,
    },
    "efficiency": {
        "asset_turnover": asset_turnover,
        "inventory_turnover": inventory_turnover,
        "cash_conversion_cycle": cash_conversion_cycle,
    },
    "safety": {
        "beta": beta,
        "altman_z_score": altman_z_score,
        "piotroski_f_score": piotroski_f_score,
        "debt_levels": debt_levels,
    },
    "dividend": {
        "dividend_yield": dividend_yield,
        "payout_ratio": payout_ratio,
        "dividend_growth_rate": dividend_growth_rate,
        "consecutive_growth_years": consecutive_growth_years,
    },
}
