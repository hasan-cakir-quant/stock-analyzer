"""Server-side MA "Normal scenario" fair value — a Python port of the
client-side MA valuation (frontend `maValuation.ts` + `valueArea.ts`).

For each method (P/E, P/B, P/S, EV/EBITDA, EV/EBIT, EV/FCF) we take the latest
trailing MA4/MA8/MA12 of the stock's own *realized* multiple, scale it by the
Normal scenario factor (×0.90, i.e. −10%), and apply it to the latest
fundamentals to get a per-share fair value. The headline fair value is the mean
of the central-70% "value area" of all those cells — matching exactly what the
MA Valuation panel shows and what a Normal-scenario snapshot would freeze.

Used by the portfolio overview to fill in a live fair price for stocks that
don't have a snapshot yet. Kept deliberately close to the TypeScript so the two
stay consistent.
"""

from __future__ import annotations

from app.services.valuations.types import Quarter

NORMAL_FACTOR = 0.9
VALUE_AREA_COVERAGE = 0.7
TTM = 4
MA_WINDOWS = (4, 8, 12)

# Scenario factors — mirror the frontend MaValuationPanel SCENARIOS so the
# portfolio jobs and the per-stock panel agree. Each factor scales the latest
# realized multiple before it's applied to the latest fundamentals.
SCENARIOS: tuple[tuple[str, float], ...] = (
    ("super_pessimist", 0.6),
    ("pessimist", 0.8),
    ("normal", 0.9),
    ("optimist", 1.0),
    ("super_optimist", 1.3),
)


def _f(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _fill_isolated_gaps(series: list[float | None]) -> list[float | None]:
    """Fill single-quarter gaps (a null with reported values on both sides)."""
    out = list(series)
    for i in range(len(out)):
        if out[i] is not None:
            continue
        prev = series[i - 1] if i > 0 else None
        nxt = series[i + 1] if i < len(series) - 1 else None
        if prev is not None and nxt is not None:
            out[i] = (prev + nxt) / 2
    return out


def _trailing_ttm(filled: list[float | None], i: int) -> float | None:
    if i < TTM - 1:
        return None
    window = filled[i - TTM + 1 : i + 1]
    if any(v is None for v in window):
        return None
    return sum(v for v in window if v is not None)


def _moving_average_at(series: list[float | None], i: int, window: int) -> float | None:
    if i < window - 1:
        return None
    chunk = series[i - window + 1 : i + 1]
    if any(v is None for v in chunk):
        return None
    return sum(v for v in chunk if v is not None) / window


def _quantile_sorted(values: list[float], q: float) -> float:
    n = len(values)
    if n == 1:
        return values[0]
    pos = (n - 1) * q
    base = int(pos)  # floor for non-negative
    rest = pos - base
    if base + 1 < n:
        return values[base] + rest * (values[base + 1] - values[base])
    return values[base]


def _value_area_mean(values: list[float]) -> float | None:
    """Mean of the central-70% band of `values` (a 70% trimmed mean)."""
    finite = sorted(v for v in values if v == v and v not in (float("inf"), float("-inf")))
    if not finite:
        return None
    tail = (1 - VALUE_AREA_COVERAGE) / 2  # 0.15
    low = _quantile_sorted(finite, tail)
    high = _quantile_sorted(finite, 1 - tail)
    in_area = [v for v in finite if low <= v <= high]
    area = in_area if in_area else finite
    return sum(area) / len(area)


def all_scenario_fair_values(
    quarters: list[Quarter], is_financial: bool
) -> dict[str, float | None]:
    """Value-area fair value per share for EVERY scenario, keyed by scenario.

    Computes the realized-multiple MAs once, then applies each scenario factor.
    `is_financial` drops the EV-based methods (they don't apply to banks).
    Returns {} when there's no data at all.
    """
    rows = sorted(quarters, key=lambda q: q.period)
    last = len(rows) - 1
    if last < 0:
        return {}

    price = [_f(r.closing_price) for r in rows]
    shares = [_f(r.shares_outstanding_diluted) for r in rows]
    eps = _fill_isolated_gaps([_f(r.eps_diluted) for r in rows])
    revenue = _fill_isolated_gaps([_f(r.revenue) for r in rows])
    ebitda = _fill_isolated_gaps([_f(r.ebitda) for r in rows])
    ebit = _fill_isolated_gaps([_f(r.operating_income) for r in rows])
    fcf = _fill_isolated_gaps([_f(r.free_cash_flow) for r in rows])

    def net_debt(r: Quarter) -> float:
        return (
            (_f(r.long_term_debt) or 0.0)
            + (_f(r.short_term_debt) or 0.0)
            - (_f(r.cash_and_equivalents) or 0.0)
        )

    ev: list[float | None] = []
    for i, r in enumerate(rows):
        if price[i] is None or shares[i] is None:
            ev.append(None)
        else:
            ev.append(price[i] * shares[i] + net_debt(r))  # type: ignore[operator]

    bvps: list[float | None] = []
    for i, r in enumerate(rows):
        eq = _f(r.total_equity)
        s = shares[i]
        bvps.append(eq / s if eq is not None and s is not None and s > 0 else None)

    sps: list[float | None] = []
    for i in range(len(rows)):
        ttm = _trailing_ttm(revenue, i)
        s = shares[i]
        sps.append(ttm / s if ttm is not None and s is not None and s > 0 else None)

    def realized_simple(per_share: list[float | None]) -> list[float | None]:
        out: list[float | None] = []
        for i in range(len(rows)):
            base = per_share[i]
            out.append(
                price[i] / base
                if price[i] is not None and base is not None and base > 0
                else None
            )
        return out

    def realized_ev(filled: list[float | None]) -> list[float | None]:
        out: list[float | None] = []
        for i in range(len(rows)):
            ttm = _trailing_ttm(filled, i)
            e = ev[i]
            out.append(
                e / ttm if e is not None and e > 0 and ttm is not None and ttm > 0 else None
            )
        return out

    # Realized P/E uses TTM EPS, so build its per-quarter "EPS per share" basis.
    realized_pe: list[float | None] = []
    for i in range(len(rows)):
        ttm = _trailing_ttm(eps, i)
        realized_pe.append(
            price[i] / ttm if price[i] is not None and ttm is not None and ttm > 0 else None
        )

    realized_pb = realized_simple(bvps)
    realized_ps = realized_simple(sps)
    realized_ev_ebitda = realized_ev(ebitda)
    realized_ev_ebit = realized_ev(ebit)
    realized_ev_fcf = realized_ev(fcf)

    # Latest fundamentals that turn a multiple into a per-share fair value.
    shares_latest = shares[last]
    net_debt_latest = net_debt(rows[last])
    ttm_eps_latest = _trailing_ttm(eps, last)
    ttm_ebitda_latest = _trailing_ttm(ebitda, last)
    ttm_ebit_latest = _trailing_ttm(ebit, last)
    ttm_fcf_latest = _trailing_ttm(fcf, last)
    bvps_latest = bvps[last]
    sps_latest = sps[last]

    def fair_simple(per_share_latest: float | None):
        return lambda m: m * per_share_latest if per_share_latest is not None else None

    def fair_ev(ttm_latest: float | None):
        def _inner(m: float) -> float | None:
            if ttm_latest is None or shares_latest is None or shares_latest <= 0:
                return None
            return (m * ttm_latest - net_debt_latest) / shares_latest

        return _inner

    methods = [
        (False, realized_pe, fair_simple(ttm_eps_latest)),
        (False, realized_pb, fair_simple(bvps_latest)),
        (False, realized_ps, fair_simple(sps_latest)),
        (True, realized_ev_ebitda, fair_ev(ttm_ebitda_latest)),
        (True, realized_ev_ebit, fair_ev(ttm_ebit_latest)),
        (True, realized_ev_fcf, fair_ev(ttm_fcf_latest)),
    ]

    # Precompute the latest MA per window per applicable method — these are
    # factor-independent, so we do it once and then apply each scenario factor.
    prepared: list[tuple[list[float], object]] = []
    for is_ev, realized, fair_value in methods:
        if is_ev and is_financial:
            continue
        raw_mas = [
            m
            for w in MA_WINDOWS
            if (m := _moving_average_at(realized, last, w)) is not None
        ]
        if raw_mas:
            prepared.append((raw_mas, fair_value))

    result: dict[str, float | None] = {}
    for key, factor in SCENARIOS:
        fairs: list[float] = []
        for raw_mas, fair_value in prepared:
            for raw_ma in raw_mas:
                fv = fair_value(raw_ma * factor)  # type: ignore[operator]
                if fv is not None and fv == fv:  # not NaN
                    fairs.append(fv)
        result[key] = _value_area_mean(fairs)
    return result


def normal_fair_value(quarters: list[Quarter], is_financial: bool) -> float | None:
    """Normal-scenario (×0.90) value-area fair value per share, or None."""
    return all_scenario_fair_values(quarters, is_financial).get("normal")
