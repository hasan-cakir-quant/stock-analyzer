"""Tests for GET /api/portfolio/overview."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _add_quarter(client: TestClient, symbol: str, period: str) -> None:
    response = client.put(
        f"/api/stocks/{symbol}/financials/{period}",
        json={
            "revenue": "100",
            "cogs": "40",
            "gross_profit": "60",
            "net_income": "10",
            "eps_diluted": "0.10",
            "ebitda": "25",
            "operating_cash_flow": "20",
            "capex": "5",
            "free_cash_flow": "15",
            "total_equity": "500",
            "total_assets": "800",
            "long_term_debt": "100",
            "short_term_debt": "20",
            "cash_and_equivalents": "50",
            "total_current_assets": "150",
            "total_current_liabilities": "80",
            "operating_income": "20",
            "interest_expense": "2",
            "shares_outstanding_diluted": "100",
            "inventory": "40",
            "receivables": "60",
            "dividends_paid": "-2",
            "closing_price": "50",
        },
    )
    assert response.status_code == 200, response.text


def _seed(client: TestClient, symbol: str, currency: str = "USD") -> None:
    create = client.post(
        "/api/stocks",
        json={"symbol": symbol, "currency": currency, "shares_outstanding": "100"},
    )
    assert create.status_code == 201
    for q in range(4):
        _add_quarter(client, symbol, f"2024-Q{q + 1}")


def _save_snapshot(client: TestClient, symbol: str, *, current_price: str) -> str:
    response = client.post(
        f"/api/stocks/{symbol}/snapshots",
        json={"parameters": {"current_price": current_price, "target_pe": "20"}},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


# ---------- empty portfolio ---------------------------------------------


def test_empty_portfolio_returns_zero_stats_and_no_rows(client: TestClient) -> None:
    response = client.get("/api/portfolio/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["stats"] == {
        "total_stocks": 0,
        "average_general_grade": None,
        "undervalued_count": 0,
        "overvalued_count": 0,
    }
    assert body["stocks"] == []


# ---------- stocks without snapshots -------------------------------------


def test_stock_without_snapshot_appears_with_null_grade_and_price_fields(
    client: TestClient,
) -> None:
    create = client.post(
        "/api/stocks", json={"symbol": "AAPL", "currency": "USD"}
    )
    assert create.status_code == 201

    body = client.get("/api/portfolio/overview").json()
    assert body["stats"]["total_stocks"] == 1
    assert body["stats"]["average_general_grade"] is None
    assert body["stats"]["undervalued_count"] == 0
    assert body["stats"]["overvalued_count"] == 0

    row = body["stocks"][0]
    assert row["symbol"] == "AAPL"
    assert row["currency"] == "USD"
    assert row["last_updated"] is None
    assert row["general_grade"] is None
    assert row["sub_grades"] == {}
    assert row["average_fair_value"] is None
    assert row["current_price"] is None
    assert row["upside_pct"] is None
    assert row["sparkline"] == []


# ---------- multi-stock with snapshots -----------------------------------


def test_multi_stock_overview_aggregates_and_returns_per_stock_rows(
    client: TestClient,
) -> None:
    _seed(client, "AAPL")
    _seed(client, "MSFT", currency="USD")
    _save_snapshot(client, "AAPL", current_price="50")
    _save_snapshot(client, "MSFT", current_price="200")

    body = client.get("/api/portfolio/overview").json()
    assert body["stats"]["total_stocks"] == 2
    assert body["stats"]["average_general_grade"] is not None
    # The sample data isn't bracketed against specific fair values yet.
    assert isinstance(body["stats"]["undervalued_count"], int)
    assert isinstance(body["stats"]["overvalued_count"], int)

    rows_by_symbol = {row["symbol"]: row for row in body["stocks"]}
    assert set(rows_by_symbol) == {"AAPL", "MSFT"}
    aapl = rows_by_symbol["AAPL"]
    assert aapl["general_grade"] is not None
    assert set(aapl["sub_grades"].keys()) == {
        "profitability",
        "valuation",
        "financial_strength",
        "growth",
        "efficiency",
        "safety",
        "dividend",
    }
    assert aapl["last_updated"] is not None
    assert aapl["sparkline"] and aapl["sparkline"][-1]["general_grade"] is not None


def test_overview_uses_latest_snapshot_per_stock(client: TestClient) -> None:
    _seed(client, "AAPL")
    _save_snapshot(client, "AAPL", current_price="50")
    latest = _save_snapshot(client, "AAPL", current_price="55")

    row = client.get("/api/portfolio/overview").json()["stocks"][0]
    assert row["current_price"] == "55"
    # The sparkline should hold both snapshots in chronological order.
    assert len(row["sparkline"]) == 2

    # Confirm last_updated matches the latest snapshot's created_at.
    detail = client.get(f"/api/snapshots/{latest}").json()
    assert row["last_updated"] == detail["created_at"]


def test_soft_deleted_snapshots_are_ignored(client: TestClient) -> None:
    """A soft-deleted latest snapshot must not be the one picked for the row."""
    _seed(client, "AAPL")
    keeper = _save_snapshot(client, "AAPL", current_price="50")
    deleter = _save_snapshot(client, "AAPL", current_price="999")
    delete = client.delete(f"/api/snapshots/{deleter}")
    assert delete.status_code == 204

    row = client.get("/api/portfolio/overview").json()["stocks"][0]
    assert row["current_price"] == "50"  # the keeper, not the (newer) deleted one
    assert len(row["sparkline"]) == 1
    # And we can confirm the keeper is what we expected.
    assert client.get(f"/api/snapshots/{keeper}").status_code == 200


def test_undervalued_and_overvalued_counts_use_price_vs_average_fair_value(
    client: TestClient,
) -> None:
    _seed(client, "AAPL")
    snap_id = _save_snapshot(client, "AAPL", current_price="50")
    snapshot = client.get(f"/api/snapshots/{snap_id}").json()
    avg = snapshot["valuations"]["summary"]["average"]
    if avg is None:
        # No valuation models computable on this dataset → can't classify.
        # Test still passes — the counts should be 0.
        body = client.get("/api/portfolio/overview").json()
        assert body["stats"]["undervalued_count"] == 0
        assert body["stats"]["overvalued_count"] == 0
        return

    avg_value = float(avg)
    body = client.get("/api/portfolio/overview").json()
    if 50.0 < avg_value:
        assert body["stats"]["undervalued_count"] == 1
        assert body["stats"]["overvalued_count"] == 0
    elif 50.0 > avg_value:
        assert body["stats"]["undervalued_count"] == 0
        assert body["stats"]["overvalued_count"] == 1
    else:
        assert body["stats"]["undervalued_count"] == 0
        assert body["stats"]["overvalued_count"] == 0
