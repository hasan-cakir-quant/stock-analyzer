"""Tests for the per-stock parameters endpoints.

Per-stock parameters now persist only market data (`current_price`, `beta`).
Valuation target multiples are transient run-time inputs and are not stored
here, so there's no global-default merge anymore.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def _create_aapl(client: TestClient) -> None:
    client.post("/api/stocks", json={"symbol": "AAPL", "currency": "USD"})


def test_get_unconfigured_stock_returns_nulls(client: TestClient) -> None:
    """An unconfigured stock returns null market-data fields and no timestamp."""
    _create_aapl(client)

    response = client.get("/api/stocks/AAPL/parameters")
    assert response.status_code == 200
    body = response.json()

    assert body["updated_at"] is None
    assert body["current_price"] is None
    assert body["beta"] is None


def test_put_then_get_round_trips(client: TestClient) -> None:
    _create_aapl(client)
    payload = {"current_price": "180.50", "beta": "1.2"}
    put = client.put("/api/stocks/AAPL/parameters", json=payload)
    assert put.status_code == 200, put.text

    refetch = client.get("/api/stocks/AAPL/parameters").json()
    assert refetch["current_price"] == "180.50"
    assert refetch["beta"] == "1.2"
    assert refetch["updated_at"] is not None


def test_subsequent_put_partial_preserves_prior_values(client: TestClient) -> None:
    """Auto-save semantics — sending one field doesn't wipe the others."""
    _create_aapl(client)
    client.put(
        "/api/stocks/AAPL/parameters",
        json={"beta": "1.1", "current_price": "200"},
    )
    client.put("/api/stocks/AAPL/parameters", json={"current_price": "210"})

    body = client.get("/api/stocks/AAPL/parameters").json()
    assert body["current_price"] == "210"
    assert body["beta"] == "1.1"


def test_get_parameters_unknown_stock_returns_404(client: TestClient) -> None:
    response = client.get("/api/stocks/UNKNOWN/parameters")
    assert response.status_code == 404


def test_put_parameters_unknown_stock_returns_404(client: TestClient) -> None:
    response = client.put(
        "/api/stocks/UNKNOWN/parameters", json={"current_price": "10"}
    )
    assert response.status_code == 404
