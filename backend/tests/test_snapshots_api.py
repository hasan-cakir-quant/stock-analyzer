"""Integration tests for POST /api/stocks/{symbol}/snapshots."""

from __future__ import annotations

from copy import deepcopy
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Snapshot


def _seed_aapl_with_four_quarters(client: TestClient) -> None:
    create = client.post(
        "/api/stocks",
        json={"symbol": "AAPL", "currency": "USD", "shares_outstanding": "100"},
    )
    assert create.status_code == 201, create.text
    for q in range(4):
        response = client.put(
            f"/api/stocks/AAPL/financials/2024-Q{q + 1}",
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


def test_create_snapshot_returns_full_payload(client: TestClient) -> None:
    _seed_aapl_with_four_quarters(client)

    response = client.post(
        "/api/stocks/AAPL/snapshots",
        json={
            "parameters": {"current_price": "60", "target_pe": "20"},
            "note": "Initial snapshot",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()

    UUID(body["id"])  # parses
    assert body["symbol"] == "AAPL"
    assert body["note"] == "Initial snapshot"
    assert body["current_price_used"] == "60"
    assert body["soft_deleted_at"] is None

    # All five JSONB blobs are non-empty / well-shaped.
    assert len(body["financials_snapshot"]) == 4
    assert body["financials_snapshot"][0]["period"] == "2024-Q1"
    assert body["parameters_used"]["target_pe"] == "20"
    assert body["settings_used"]["id"] == 1
    assert "models" in body["valuations"] and "summary" in body["valuations"]
    assert set(body["grades"]["sub_grades"].keys()) == {
        "profitability",
        "valuation",
        "financial_strength",
        "growth",
        "efficiency",
        "safety",
        "dividend",
    }
    assert body["growth_metrics"]["horizons"] == ["1Y", "3Y", "5Y", "10Y"]


def test_snapshot_is_immutable_when_underlying_financials_change(
    client: TestClient, db_session: Session
) -> None:
    """DoD: edit a financial → re-fetch snapshot → values unchanged."""
    _seed_aapl_with_four_quarters(client)
    create = client.post(
        "/api/stocks/AAPL/snapshots",
        json={"parameters": {"current_price": "60", "target_pe": "20"}},
    )
    assert create.status_code == 201
    snapshot_id = UUID(create.json()["id"])
    original_financials = deepcopy(create.json()["financials_snapshot"])
    original_pe_fair_value = create.json()["valuations"]["models"]["pe_based"]["fair_value"]

    # Mutate the underlying quarter — revenue triples, gross profit triples.
    edit = client.put(
        "/api/stocks/AAPL/financials/2024-Q1",
        json={"revenue": "300", "gross_profit": "180"},
    )
    assert edit.status_code == 200

    # Re-load the snapshot from the DB and verify the JSONB columns are
    # untouched. We use db_session directly (the conftest's `client` fixture
    # routes endpoint queries through the same session), so the snapshot
    # row created above is visible here.
    db_session.expire_all()
    persisted = db_session.get(Snapshot, snapshot_id)
    assert persisted is not None

    snapshot_q1 = next(
        q for q in persisted.financials_snapshot if q["period"] == "2024-Q1"
    )
    original_q1 = next(q for q in original_financials if q["period"] == "2024-Q1")
    assert snapshot_q1["revenue"] == original_q1["revenue"] == "100"
    assert snapshot_q1["gross_profit"] == original_q1["gross_profit"] == "60"

    # And the computed valuations recorded at snapshot time are unchanged.
    assert (
        persisted.valuations["models"]["pe_based"]["fair_value"]
        == original_pe_fair_value
    )


def test_snapshot_is_immutable_when_settings_change(
    client: TestClient, db_session: Session
) -> None:
    _seed_aapl_with_four_quarters(client)
    create = client.post(
        "/api/stocks/AAPL/snapshots",
        json={"parameters": {"current_price": "60", "target_pe": "20"}},
    )
    snapshot_id = UUID(create.json()["id"])
    original_settings = deepcopy(create.json()["settings_used"])

    # Push a new settings payload with different general weights / market assumptions.
    seed = client.get("/api/settings").json()
    seed.pop("id", None)
    seed.pop("updated_at", None)
    seed["global_market_assumptions"]["target_pe"] = "9.9"
    seed["general_grade_weights"]["profitability"] = "30"
    seed["general_grade_weights"]["valuation"] = "10"  # rebalance to sum to 100
    put_settings = client.put("/api/settings", json=seed)
    assert put_settings.status_code == 200, put_settings.text

    db_session.expire_all()
    persisted = db_session.get(Snapshot, snapshot_id)
    assert persisted is not None
    # Frozen settings are still the original values.
    assert (
        persisted.settings_used["global_market_assumptions"]["target_pe"]
        == original_settings["global_market_assumptions"]["target_pe"]
    )
    assert (
        persisted.settings_used["general_grade_weights"]["profitability"]
        == original_settings["general_grade_weights"]["profitability"]
    )


def test_create_snapshot_unknown_stock_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/stocks/UNKNOWN/snapshots", json={"parameters": {"current_price": "10"}}
    )
    assert response.status_code == 404


def test_create_snapshot_with_no_parameters_uses_global_defaults(
    client: TestClient,
) -> None:
    """An empty body still works — defaults flow in from settings."""
    _seed_aapl_with_four_quarters(client)
    response = client.post("/api/stocks/AAPL/snapshots", json={})
    assert response.status_code == 201, response.text
    # parameters_used should at least have the seeded global defaults.
    params = response.json()["parameters_used"]
    assert params["target_pe"] == "18"  # seeded default
