"""Integration test for POST /api/stocks/{symbol}/analyze."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _seed_aapl_with_twelve_quarters(client: TestClient) -> None:
    create = client.post(
        "/api/stocks",
        json={
            "symbol": "AAPL",
            "currency": "USD",
            "shares_outstanding": "100",
        },
    )
    assert create.status_code == 201, create.text

    # 3 years × 4 quarters with 10% YoY growth on every relevant line item.
    for year_idx, factor in enumerate((1.0, 1.10, 1.21)):
        year = 2022 + year_idx
        for q in range(4):
            response = client.put(
                f"/api/stocks/AAPL/financials/{year}-Q{q + 1}",
                json={
                    "revenue": str(100 * factor),
                    "cogs": str(40 * factor),
                    "gross_profit": str(60 * factor),
                    "operating_income": str(20 * factor),
                    "interest_expense": str(2 * factor),
                    "net_income": str(10 * factor),
                    "eps_diluted": str(0.10 * factor),
                    "ebitda": str(25 * factor),
                    "shares_outstanding_diluted": "100",
                    "cash_and_equivalents": str(50 * factor),
                    "short_term_investments": "0",
                    "total_current_assets": str(150 * factor),
                    "total_assets": str(800 * factor),
                    "short_term_debt": str(20 * factor),
                    "total_current_liabilities": str(80 * factor),
                    "long_term_debt": str(100 * factor),
                    "total_equity": str(500 * factor),
                    "inventory": str(40 * factor),
                    "receivables": str(60 * factor),
                    "operating_cash_flow": str(20 * factor),
                    "capex": str(5 * factor),
                    "free_cash_flow": str(15 * factor),
                    "dividends_paid": str(-2 * factor),
                    "closing_price": str(50 * factor),
                },
            )
            assert response.status_code == 200, response.text


def test_analyze_returns_valuations_grades_and_growth_for_seeded_stock(
    client: TestClient,
) -> None:
    _seed_aapl_with_twelve_quarters(client)

    response = client.post(
        "/api/stocks/AAPL/analyze",
        json={
            "current_price": "60",
            "target_pe": "20",
            "target_ev_ebitda": "10",
            "beta": "1.1",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()

    # Top-level shape.
    assert body["symbol"] == "AAPL"
    assert body["current_price"] == 60.0
    assert {"valuations", "grades", "growth"} <= set(body)

    # Valuations: both models returned, summary populated.
    val_models = body["valuations"]["models"]
    assert set(val_models) == {
        "pe_based",
        "pb_based",
        "ev_ebitda",
        "ev_ebit",
        "ev_fcf",
    }
    summary = body["valuations"]["summary"]
    assert summary["current_price"] == 60.0
    # At least the simple multiples should be computable here.
    assert val_models["pe_based"]["computable"] is True
    assert val_models["ev_ebitda"]["computable"] is True
    assert summary["average"] is not None
    assert summary["upside_pct"] is not None

    # P/E sanity check: TTM EPS = 4 × (0.10 × 1.21) = 0.484. fair = 0.484 × 20 = 9.68.
    assert abs(val_models["pe_based"]["fair_value"] - 9.68) < 1e-2

    # Grades: §5.2 shape, all seven sub-grades present.
    grades = body["grades"]
    assert set(grades["sub_grades"].keys()) == {
        "profitability",
        "valuation",
        "financial_strength",
        "growth",
        "efficiency",
        "safety",
        "dividend",
    }
    # General grade is a number when at least one sub-grade scored.
    assert isinstance(grades["general"], (int, float))

    # Growth: every metric in the table; 1Y CAGRs ≈ 10% for the constant-growth dataset.
    growth = body["growth"]
    assert growth["horizons"] == ["1Y", "3Y", "5Y", "10Y"]
    assert "revenue" in growth["metrics"]
    assert abs(growth["metrics"]["revenue"]["1Y"] - 0.10) < 1e-3
    # 3Y / 5Y / 10Y all need more than 12 quarters → null.
    assert growth["metrics"]["revenue"]["3Y"] is None


def test_analyze_falls_back_to_global_defaults_when_body_omits_field(
    client: TestClient,
) -> None:
    _seed_aapl_with_twelve_quarters(client)

    # Body omits target_pe — global default (18) should fill in, so pe_based stays computable.
    response = client.post(
        "/api/stocks/AAPL/analyze",
        json={"current_price": "60"},
    )
    assert response.status_code == 200
    pe = response.json()["valuations"]["models"]["pe_based"]
    assert pe["computable"] is True
    # TTM EPS = 0.484, default target_pe from settings = 18 → 0.484 × 18 = 8.712.
    assert abs(pe["fair_value"] - 8.712) < 1e-2


def test_analyze_unknown_stock_returns_404(client: TestClient) -> None:
    response = client.post("/api/stocks/UNKNOWN/analyze", json={"current_price": "10"})
    assert response.status_code == 404
