"""Unit tests for the growth-metrics calculator.

Covers the CAGR helper, flow/stock/trend computations, full vs partial
history, exactly-at-boundary cases, and the 12-quarter DoD fixture.
"""

from __future__ import annotations

from decimal import Decimal

from app.services.growth import GrowthInputs, compute_growth, to_payload
from app.services.growth.calculator import _cagr
from app.services.valuations import Quarter


def _q(period: str, **fields) -> Quarter:
    coerced = {k: (None if v is None else Decimal(str(v))) for k, v in fields.items()}
    return Quarter(period=period, **coerced)


def _approx(value: Decimal | None, expected: float, tol: float = 1e-6) -> bool:
    return value is not None and abs(float(value) - expected) < tol


# ---------- CAGR helper ---------------------------------------------------


def test_cagr_basic() -> None:
    # 100 → 121 over 2 years = 10%
    assert _approx(_cagr(Decimal(100), Decimal(121), 2), 0.10)


def test_cagr_returns_none_on_non_positive_inputs() -> None:
    assert _cagr(Decimal(0), Decimal(100), 1) is None
    assert _cagr(Decimal(100), Decimal(-50), 1) is None
    assert _cagr(Decimal(100), Decimal(110), 0) is None


# ---------- flow growth ---------------------------------------------------


def _flat_year(year: str, revenue: float, count: int = 4) -> list[Quarter]:
    return [_q(f"{year}-Q{i + 1}", revenue=revenue) for i in range(count)]


def test_flow_growth_one_year() -> None:
    # Year 1: 100/q (TTM 400). Year 2: 110/q (TTM 440). 1Y = 10%.
    quarters = _flat_year("2023", 100) + _flat_year("2024", 110)
    result = compute_growth(GrowthInputs(quarters=quarters))
    assert _approx(result.metrics["revenue"].values[1], 0.10)
    # 3Y/5Y/10Y need more history → N/A.
    assert result.metrics["revenue"].values[3] is None
    assert result.metrics["revenue"].values[5] is None
    assert result.metrics["revenue"].values[10] is None


def test_flow_growth_three_year_with_16_quarters() -> None:
    """16 quarters → 3Y CAGR computable. 100→133.1 over 3 years = 10%."""
    quarters = (
        _flat_year("2021", 100)
        + _flat_year("2022", 110)
        + _flat_year("2023", 121)
        + _flat_year("2024", 133.1)
    )
    result = compute_growth(GrowthInputs(quarters=quarters))
    assert _approx(result.metrics["revenue"].values[3], 0.10, tol=1e-4)
    # 1Y is also computable here (133.1 / 121 - 1 ≈ 0.10).
    assert _approx(result.metrics["revenue"].values[1], 0.10, tol=1e-4)


def test_flow_growth_exact_boundary_eight_quarters_yields_1y_only() -> None:
    quarters = _flat_year("2023", 100) + _flat_year("2024", 105)
    assert len(quarters) == 8
    result = compute_growth(GrowthInputs(quarters=quarters))
    assert _approx(result.metrics["revenue"].values[1], 0.05, tol=1e-4)
    assert result.metrics["revenue"].values[3] is None


def test_flow_growth_seven_quarters_yields_no_1y() -> None:
    quarters = _flat_year("2023", 100) + _flat_year("2024", 105, count=3)
    assert len(quarters) == 7
    result = compute_growth(GrowthInputs(quarters=quarters))
    assert result.metrics["revenue"].values[1] is None


# ---------- stock growth (book value via total_equity) -------------------


def test_book_value_per_share_growth_uses_point_in_time_equity() -> None:
    """5 quarters: equity at idx -5 = 100, idx -1 = 110 → 1Y = 10%."""
    quarters = [
        _q("2023-Q4", total_equity=100),
        _q("2024-Q1", total_equity=102),
        _q("2024-Q2", total_equity=104),
        _q("2024-Q3", total_equity=106),
        _q("2024-Q4", total_equity=110),
    ]
    result = compute_growth(GrowthInputs(quarters=quarters))
    assert _approx(result.metrics["book_value_per_share"].values[1], 0.10, tol=1e-4)
    assert result.metrics["book_value_per_share"].values[3] is None


def test_book_value_growth_needs_one_more_quarter_than_horizon() -> None:
    """Stock growth needs 4*N + 1 quarters; 4 quarters is one short for 1Y."""
    quarters = [_q(f"2024-Q{i + 1}", total_equity=100 + i) for i in range(4)]
    result = compute_growth(GrowthInputs(quarters=quarters))
    assert result.metrics["book_value_per_share"].values[1] is None


# ---------- trends --------------------------------------------------------


def _year_with_margin(year: str, revenue: float, gross_profit: float) -> list[Quarter]:
    return [
        _q(f"{year}-Q{i + 1}", revenue=revenue, gross_profit=gross_profit)
        for i in range(4)
    ]


def test_gross_margin_trend_is_pct_point_delta() -> None:
    # Year 1: 1000 rev, 400 GP → 40% GM. Year 2: 1100 rev, 550 GP → 50% GM. Δ = +10pp.
    quarters = _year_with_margin("2023", 250, 100) + _year_with_margin("2024", 275, 137.5)
    result = compute_growth(GrowthInputs(quarters=quarters))
    assert _approx(result.metrics["gross_margin_trend"].values[1], 0.10, tol=1e-4)


def test_roe_trend_is_pct_point_delta() -> None:
    """8 quarters. Year 1 NI=25/q (TTM 100), equity at idx 3 = 1000 → ROE 10%.
    Year 2 NI=37.5/q (TTM 150), equity at idx 7 = 1000 → ROE 15%. Δ = +5pp.
    """
    year1 = [_q(f"2023-Q{i + 1}", net_income=25, total_equity=1000) for i in range(4)]
    year2 = [_q(f"2024-Q{i + 1}", net_income=37.5, total_equity=1000) for i in range(4)]
    result = compute_growth(GrowthInputs(quarters=year1 + year2))
    assert _approx(result.metrics["roe_trend"].values[1], 0.05, tol=1e-4)


# ---------- dividend per share (uses abs of cashflow sign) ---------------


def test_dividend_per_share_growth_handles_negative_cashflow_signs() -> None:
    year1 = [_q(f"2023-Q{i + 1}", dividends_paid=-10) for i in range(4)]  # TTM 40
    year2 = [_q(f"2024-Q{i + 1}", dividends_paid=-11) for i in range(4)]  # TTM 44
    result = compute_growth(GrowthInputs(quarters=year1 + year2))
    assert _approx(result.metrics["dividend_per_share"].values[1], 0.10, tol=1e-4)


# ---------- DoD: 12-quarter synthetic dataset ----------------------------


def _twelve_quarter_dataset() -> list[Quarter]:
    """3 years × 4 quarters with consistent 10% YoY growth on every metric.

    All flows step from year-1 → year-2 → year-3 by *1.10 each year, so:
      1Y CAGR ≈ 10% (same step both years).
      Stock metrics (equity) grow 100 → 110 → 121 across year-end snapshots.
    """
    out: list[Quarter] = []
    for year_idx, factor in enumerate((1.0, 1.10, 1.21)):
        year = 2022 + year_idx
        for q in range(4):
            out.append(
                _q(
                    f"{year}-Q{q + 1}",
                    revenue=100 * factor,
                    net_income=10 * factor,
                    ebitda=20 * factor,
                    eps_diluted=0.5 * factor,
                    free_cash_flow=8 * factor,
                    operating_cash_flow=12 * factor,
                    dividends_paid=-2 * factor,
                    total_equity=100 * factor,
                    gross_profit=40 * factor,
                    operating_income=15 * factor,
                )
            )
    return out


def test_dod_twelve_quarter_dataset_returns_expected_one_year_cagrs() -> None:
    quarters = _twelve_quarter_dataset()
    assert len(quarters) == 12
    result = compute_growth(GrowthInputs(quarters=quarters))

    # Every flow metric grew exactly 10% YoY.
    for metric in (
        "revenue",
        "net_income",
        "ebitda",
        "eps_diluted",
        "free_cash_flow",
        "operating_cash_flow",
        "dividend_per_share",
    ):
        assert _approx(
            result.metrics[metric].values[1], 0.10, tol=1e-4
        ), f"{metric} 1Y CAGR off"
        # 3Y / 5Y / 10Y all need more than 12 quarters → N/A.
        assert result.metrics[metric].values[3] is None
        assert result.metrics[metric].values[5] is None
        assert result.metrics[metric].values[10] is None

    # Book value grew 10% per year as well; with 12 quarters we get 1Y and 2Y
    # only — but the table reports 1Y / 3Y / 5Y / 10Y, so 3Y still N/A.
    assert _approx(result.metrics["book_value_per_share"].values[1], 0.10, tol=1e-4)
    assert result.metrics["book_value_per_share"].values[3] is None

    # Margins are constant ratios across years (everything scaled by the same
    # factor) → trend deltas are 0.
    assert _approx(result.metrics["gross_margin_trend"].values[1], 0.0, tol=1e-9)
    assert _approx(result.metrics["operating_margin_trend"].values[1], 0.0, tol=1e-9)


# ---------- payload shape -------------------------------------------------


def test_to_payload_uses_horizon_strings_and_floats() -> None:
    quarters = _flat_year("2023", 100) + _flat_year("2024", 110)
    payload = to_payload(compute_growth(GrowthInputs(quarters=quarters)))
    assert payload["horizons"] == ["1Y", "3Y", "5Y", "10Y"]
    revenue = payload["metrics"]["revenue"]
    assert set(revenue.keys()) == {"1Y", "3Y", "5Y", "10Y"}
    assert isinstance(revenue["1Y"], float)
    assert revenue["3Y"] is None
