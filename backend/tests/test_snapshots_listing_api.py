"""Tests for snapshot listing, detail, comparison, and delete endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _create_stock(client: TestClient, symbol: str) -> None:
    create = client.post(
        "/api/stocks",
        json={"symbol": symbol, "currency": "USD", "shares_outstanding": "100"},
    )
    assert create.status_code == 201, create.text


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


def _seed_with_four_quarters(client: TestClient, symbol: str) -> None:
    _create_stock(client, symbol)
    for q in range(4):
        _add_quarter(client, symbol, f"2024-Q{q + 1}")


def _save_snapshot(client: TestClient, symbol: str, *, current_price: str, note: str | None = None) -> str:
    body: dict = {"parameters": {"current_price": current_price, "target_pe": "20"}}
    if note is not None:
        body["note"] = note
    response = client.post(f"/api/stocks/{symbol}/snapshots", json=body)
    assert response.status_code == 201, response.text
    return response.json()["id"]


# ---------- per-stock list ----------------------------------------------


def test_per_stock_list_returns_snapshots_in_descending_order(client: TestClient) -> None:
    _seed_with_four_quarters(client, "AAPL")
    id_1 = _save_snapshot(client, "AAPL", current_price="50")
    id_2 = _save_snapshot(client, "AAPL", current_price="55")
    id_3 = _save_snapshot(client, "AAPL", current_price="60")

    response = client.get("/api/stocks/AAPL/snapshots")
    assert response.status_code == 200
    ids = [row["id"] for row in response.json()]
    assert ids == [id_3, id_2, id_1]

    # Denormalised list-item fields are present.
    row = response.json()[0]
    assert row["general_grade"] is not None
    assert row["average_fair_value"] is not None
    assert row["current_price_used"] == "60"


def test_per_stock_list_excludes_soft_deleted_by_default(client: TestClient) -> None:
    _seed_with_four_quarters(client, "AAPL")
    keeper = _save_snapshot(client, "AAPL", current_price="55")
    deleter = _save_snapshot(client, "AAPL", current_price="60")

    delete = client.delete(f"/api/snapshots/{deleter}")
    assert delete.status_code == 204

    visible = client.get("/api/stocks/AAPL/snapshots").json()
    assert [row["id"] for row in visible] == [keeper]

    # Toggling the include flag brings it back.
    all_rows = client.get("/api/stocks/AAPL/snapshots", params={"include_deleted": True}).json()
    assert {row["id"] for row in all_rows} == {keeper, deleter}


def test_per_stock_list_unknown_stock_returns_404(client: TestClient) -> None:
    response = client.get("/api/stocks/UNKNOWN/snapshots")
    assert response.status_code == 404


# ---------- cross-stock list --------------------------------------------


def test_cross_stock_list_returns_all_symbols(client: TestClient) -> None:
    _seed_with_four_quarters(client, "AAPL")
    _seed_with_four_quarters(client, "MSFT")
    _save_snapshot(client, "AAPL", current_price="50")
    _save_snapshot(client, "MSFT", current_price="200")

    response = client.get("/api/snapshots")
    assert response.status_code == 200
    symbols = {row["symbol"] for row in response.json()}
    assert symbols == {"AAPL", "MSFT"}


def test_cross_stock_list_filters_by_symbol_substring_case_insensitively(
    client: TestClient,
) -> None:
    _seed_with_four_quarters(client, "AAPL")
    _seed_with_four_quarters(client, "GOOG")
    _save_snapshot(client, "AAPL", current_price="50")
    _save_snapshot(client, "GOOG", current_price="100")

    response = client.get("/api/snapshots", params={"symbol": "aap"})
    assert response.status_code == 200
    assert {row["symbol"] for row in response.json()} == {"AAPL"}


def test_cross_stock_list_filters_by_grade_range(client: TestClient) -> None:
    """Save two snapshots with different grades and bracket one out."""
    _seed_with_four_quarters(client, "AAPL")
    _save_snapshot(client, "AAPL", current_price="50")
    _save_snapshot(client, "AAPL", current_price="50")

    full = client.get("/api/snapshots").json()
    grades = sorted(float(r["general_grade"]) for r in full)
    assert len(grades) == 2

    # `grade_max=0` excludes anything with a positive general grade — both go.
    excluded = client.get("/api/snapshots", params={"grade_max": 0}).json()
    assert excluded == []

    # Full window 0-100 → both back.
    included = client.get("/api/snapshots", params={"grade_min": 0, "grade_max": 100}).json()
    assert len(included) == 2


def test_cross_stock_list_excludes_soft_deleted_by_default(client: TestClient) -> None:
    _seed_with_four_quarters(client, "AAPL")
    visible = _save_snapshot(client, "AAPL", current_price="50")
    gone = _save_snapshot(client, "AAPL", current_price="60")
    client.delete(f"/api/snapshots/{gone}")

    rows = client.get("/api/snapshots").json()
    assert [r["id"] for r in rows] == [visible]

    rows_all = client.get("/api/snapshots", params={"include_deleted": True}).json()
    assert {r["id"] for r in rows_all} == {visible, gone}


# ---------- detail -------------------------------------------------------


def test_get_detail_returns_full_snapshot(client: TestClient) -> None:
    _seed_with_four_quarters(client, "AAPL")
    snap_id = _save_snapshot(client, "AAPL", current_price="60", note="thesis v1")

    response = client.get(f"/api/snapshots/{snap_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == snap_id
    assert body["note"] == "thesis v1"
    assert len(body["financials_snapshot"]) == 4
    assert "models" in body["valuations"]
    assert "sub_grades" in body["grades"]
    assert body["growth_metrics"]["horizons"] == ["1Y", "3Y", "5Y", "10Y"]


def test_get_detail_unknown_returns_404(client: TestClient) -> None:
    response = client.get("/api/snapshots/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


# ---------- compare ------------------------------------------------------


def test_compare_returns_deltas_for_known_numeric_fields(client: TestClient) -> None:
    _seed_with_four_quarters(client, "AAPL")
    a = _save_snapshot(client, "AAPL", current_price="50")
    b = _save_snapshot(client, "AAPL", current_price="60")

    response = client.post(
        "/api/snapshots/compare",
        json={"snapshot_id_a": a, "snapshot_id_b": b},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["a"]["id"] == a
    assert body["b"]["id"] == b

    deltas = body["deltas"]
    # current_price changed from 50 → 60 → +10 delta on the summary.
    assert abs(deltas["current_price"] - 10.0) < 1e-6
    # Same data → same general grade → 0 delta (or null if Incomplete on both).
    assert deltas["general_grade"] in (0.0, None)
    # The pe_based fair value is identical → 0 delta.
    assert deltas["valuation_models"]["pe_based"] in (0.0, None)
    # Sub-grade deltas keyed by name.
    assert "profitability" in deltas["sub_grades"]


def test_compare_with_unknown_id_returns_404(client: TestClient) -> None:
    _seed_with_four_quarters(client, "AAPL")
    real = _save_snapshot(client, "AAPL", current_price="50")
    response = client.post(
        "/api/snapshots/compare",
        json={
            "snapshot_id_a": real,
            "snapshot_id_b": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert response.status_code == 404


# ---------- delete -------------------------------------------------------


def test_soft_delete_marks_row_and_hides_from_listing(client: TestClient) -> None:
    _seed_with_four_quarters(client, "AAPL")
    snap_id = _save_snapshot(client, "AAPL", current_price="50")

    delete = client.delete(f"/api/snapshots/{snap_id}")
    assert delete.status_code == 204

    # Detail still resolves (soft-deleted snapshots are recoverable).
    detail = client.get(f"/api/snapshots/{snap_id}").json()
    assert detail["soft_deleted_at"] is not None

    # Default list hides it.
    visible = client.get("/api/stocks/AAPL/snapshots").json()
    assert visible == []


def test_hard_delete_requires_soft_delete_first(client: TestClient) -> None:
    _seed_with_four_quarters(client, "AAPL")
    snap_id = _save_snapshot(client, "AAPL", current_price="50")

    too_soon = client.delete(f"/api/snapshots/{snap_id}/hard")
    assert too_soon.status_code == 409

    soft = client.delete(f"/api/snapshots/{snap_id}")
    assert soft.status_code == 204

    hard = client.delete(f"/api/snapshots/{snap_id}/hard")
    assert hard.status_code == 204

    # Row is gone for real now.
    gone = client.get(f"/api/snapshots/{snap_id}")
    assert gone.status_code == 404


def test_delete_unknown_returns_404(client: TestClient) -> None:
    response = client.delete("/api/snapshots/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    response_hard = client.delete(
        "/api/snapshots/00000000-0000-0000-0000-000000000000/hard"
    )
    assert response_hard.status_code == 404
