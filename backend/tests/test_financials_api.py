"""Tests for the quarterly financials endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _create_aapl(client: TestClient) -> None:
    client.post("/api/stocks", json={"symbol": "AAPL", "currency": "USD"})


def test_put_then_get_round_trips_one_quarter(client: TestClient) -> None:
    _create_aapl(client)
    put = client.put(
        "/api/stocks/AAPL/financials/2024-Q1",
        json={
            "period_end_date": "2024-03-31",
            "revenue": "100000",
            "cogs": "60000",
            "net_income": "20000",
        },
    )
    assert put.status_code == 200, put.text

    listing = client.get("/api/stocks/AAPL/financials").json()
    assert len(listing) == 1
    row = listing[0]
    assert row["period"] == "2024-Q1"
    assert row["revenue"] == "100000"
    assert row["cogs"] == "60000"
    assert row["net_income"] == "20000"


def test_put_twelve_quarters_in_sequence(client: TestClient) -> None:
    """Definition of done — 12 sequential quarters round-trip fully."""
    _create_aapl(client)

    expected: list[str] = []
    for year in (2022, 2023, 2024):
        for q in (1, 2, 3, 4):
            period = f"{year}-Q{q}"
            expected.append(period)
            response = client.put(
                f"/api/stocks/AAPL/financials/{period}",
                json={
                    "revenue": str(100000 + len(expected) * 1000),
                    "cogs": str(60000 + len(expected) * 500),
                    "net_income": str(15000 + len(expected) * 100),
                },
            )
            assert response.status_code == 200, response.text

    rows = client.get("/api/stocks/AAPL/financials").json()
    assert [r["period"] for r in rows] == expected
    # Spot-check a row from the middle is correct.
    mid = next(r for r in rows if r["period"] == "2023-Q2")
    # 2023-Q2 is the 6th period in iteration order — index 5, so len==6 there.
    assert mid["revenue"] == "106000"
    assert mid["cogs"] == "63000"


def test_put_partial_update_preserves_unsent_fields(client: TestClient) -> None:
    _create_aapl(client)
    client.put(
        "/api/stocks/AAPL/financials/2024-Q1",
        json={"revenue": "100000", "cogs": "60000", "net_income": "20000"},
    )
    # Auto-save sends just the changed cell — net_income & cogs must persist.
    second = client.put(
        "/api/stocks/AAPL/financials/2024-Q1",
        json={"revenue": "110000"},
    )
    assert second.status_code == 200
    body = second.json()
    assert body["revenue"] == "110000"
    assert body["cogs"] == "60000"
    assert body["net_income"] == "20000"


def test_derives_gross_profit_when_null(client: TestClient) -> None:
    _create_aapl(client)
    response = client.put(
        "/api/stocks/AAPL/financials/2024-Q1",
        json={"revenue": "100000", "cogs": "40000"},
    )
    assert response.status_code == 200
    assert response.json()["gross_profit"] == "60000"


def test_derives_free_cash_flow_when_null(client: TestClient) -> None:
    _create_aapl(client)
    response = client.put(
        "/api/stocks/AAPL/financials/2024-Q1",
        json={"operating_cash_flow": "30000", "capex": "8000"},
    )
    assert response.status_code == 200
    assert response.json()["free_cash_flow"] == "22000"


def test_user_supplied_gross_profit_is_not_overwritten(client: TestClient) -> None:
    _create_aapl(client)
    response = client.put(
        "/api/stocks/AAPL/financials/2024-Q1",
        json={"revenue": "100000", "cogs": "40000", "gross_profit": "55000"},
    )
    assert response.status_code == 200
    # Spec: "otherwise respect the user's value" — 55000 wins, not 60000.
    assert response.json()["gross_profit"] == "55000"


def test_user_supplied_free_cash_flow_is_not_overwritten(client: TestClient) -> None:
    _create_aapl(client)
    response = client.put(
        "/api/stocks/AAPL/financials/2024-Q1",
        json={"operating_cash_flow": "30000", "capex": "8000", "free_cash_flow": "20000"},
    )
    assert response.status_code == 200
    assert response.json()["free_cash_flow"] == "20000"


def test_derives_eps_diluted_from_per_quarter_shares(client: TestClient) -> None:
    """When the quarter has shares_outstanding_diluted, that's what EPS uses."""
    _create_aapl(client)
    response = client.put(
        "/api/stocks/AAPL/financials/2024-Q1",
        json={"net_income": "1000", "shares_outstanding_diluted": "200"},
    )
    assert response.status_code == 200
    # 1000 / 200 = 5.0 — Decimal division renders without trailing zeros stripped.
    assert response.json()["eps_diluted"] == "5"


def test_derives_eps_diluted_from_stock_level_shares_when_quarter_shares_missing(
    client: TestClient,
) -> None:
    """Users who entered shares once on the stock metadata don't have to repeat it."""
    create = client.post(
        "/api/stocks",
        json={"symbol": "AAPL", "currency": "USD", "shares_outstanding": "500"},
    )
    assert create.status_code == 201

    response = client.put(
        "/api/stocks/AAPL/financials/2024-Q1",
        json={"net_income": "2500"},
    )
    assert response.status_code == 200
    # 2500 / 500 = 5
    assert response.json()["eps_diluted"] == "5"


def test_user_supplied_eps_diluted_is_not_overwritten(client: TestClient) -> None:
    _create_aapl(client)
    response = client.put(
        "/api/stocks/AAPL/financials/2024-Q1",
        json={
            "net_income": "1000",
            "shares_outstanding_diluted": "200",
            "eps_diluted": "4.5",
        },
    )
    assert response.status_code == 200
    assert response.json()["eps_diluted"] == "4.5"


def test_eps_not_derived_without_any_shares_source(client: TestClient) -> None:
    """No per-quarter diluted shares AND no stock-level shares → EPS stays null."""
    _create_aapl(client)  # AAPL is created without shares_outstanding here.
    response = client.put(
        "/api/stocks/AAPL/financials/2024-Q1",
        json={"net_income": "1000"},
    )
    assert response.status_code == 200
    assert response.json()["eps_diluted"] is None


def test_derivation_does_not_run_when_input_missing(client: TestClient) -> None:
    _create_aapl(client)
    response = client.put(
        "/api/stocks/AAPL/financials/2024-Q1",
        json={"revenue": "100000"},
    )
    assert response.status_code == 200
    assert response.json()["gross_profit"] is None


def test_list_financials_unknown_stock_returns_404(client: TestClient) -> None:
    response = client.get("/api/stocks/UNKNOWN/financials")
    assert response.status_code == 404


def test_put_financial_unknown_stock_returns_404(client: TestClient) -> None:
    response = client.put(
        "/api/stocks/UNKNOWN/financials/2024-Q1",
        json={"revenue": "100"},
    )
    assert response.status_code == 404


def test_delete_financial_removes_row(client: TestClient) -> None:
    _create_aapl(client)
    client.put(
        "/api/stocks/AAPL/financials/2024-Q1",
        json={"revenue": "100"},
    )
    assert len(client.get("/api/stocks/AAPL/financials").json()) == 1

    response = client.delete("/api/stocks/AAPL/financials/2024-Q1")
    assert response.status_code == 204

    assert client.get("/api/stocks/AAPL/financials").json() == []


def test_delete_financial_unknown_quarter_returns_404(client: TestClient) -> None:
    _create_aapl(client)
    response = client.delete("/api/stocks/AAPL/financials/2024-Q1")
    assert response.status_code == 404


def test_delete_financial_unknown_stock_returns_404(client: TestClient) -> None:
    response = client.delete("/api/stocks/UNKNOWN/financials/2024-Q1")
    assert response.status_code == 404


def test_delete_financial_invalid_period_returns_422(client: TestClient) -> None:
    _create_aapl(client)
    response = client.delete("/api/stocks/AAPL/financials/2024Q1")
    assert response.status_code == 422


def test_put_invalid_period_returns_422(client: TestClient) -> None:
    _create_aapl(client)
    response = client.put(
        "/api/stocks/AAPL/financials/2024Q1",  # missing dash
        json={"revenue": "100"},
    )
    assert response.status_code == 422
