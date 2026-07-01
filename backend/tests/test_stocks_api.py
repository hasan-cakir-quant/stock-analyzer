"""Tests for the stocks endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_create_stock_returns_201_and_normalises_symbol(client: TestClient) -> None:
    response = client.post(
        "/api/stocks",
        json={
            "symbol": "aapl",
            "currency": "USD",
            "shares_outstanding": "15500000000",
            "notes": "## Thesis\n* dominant ecosystem",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["symbol"] == "AAPL"
    assert body["currency"] == "USD"
    assert body["shares_outstanding"] == "15500000000"
    assert body["notes"].startswith("## Thesis")
    assert body["id"]
    assert body["created_at"]


def test_create_stock_duplicate_symbol_returns_409(client: TestClient) -> None:
    client.post("/api/stocks", json={"symbol": "AAPL", "currency": "USD"})
    duplicate = client.post(
        "/api/stocks", json={"symbol": "aapl", "currency": "USD"}
    )
    assert duplicate.status_code == 409
    assert "already exists" in duplicate.json()["detail"]


def test_list_stocks_returns_all_ordered_by_symbol(client: TestClient) -> None:
    for symbol in ("MSFT", "AAPL", "GOOG"):
        client.post("/api/stocks", json={"symbol": symbol, "currency": "USD"})

    response = client.get("/api/stocks")
    assert response.status_code == 200
    symbols = [row["symbol"] for row in response.json()]
    assert symbols == ["AAPL", "GOOG", "MSFT"]


def test_get_stock_by_symbol_is_case_insensitive(client: TestClient) -> None:
    client.post("/api/stocks", json={"symbol": "AAPL", "currency": "USD"})

    upper = client.get("/api/stocks/AAPL")
    lower = client.get("/api/stocks/aapl")
    assert upper.status_code == 200
    assert lower.status_code == 200
    assert upper.json()["id"] == lower.json()["id"]


def test_get_stock_unknown_symbol_returns_404(client: TestClient) -> None:
    response = client.get("/api/stocks/NOPE")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_patch_stock_updates_notes_and_shares(client: TestClient) -> None:
    client.post(
        "/api/stocks",
        json={
            "symbol": "AAPL",
            "currency": "USD",
            "shares_outstanding": "15500000000",
            "notes": "old",
        },
    )

    response = client.patch(
        "/api/stocks/AAPL",
        json={"notes": "new thesis", "shares_outstanding": "15400000000"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["notes"] == "new thesis"
    assert body["shares_outstanding"] == "15400000000"
    # Currency was untouched.
    assert body["currency"] == "USD"


def test_patch_stock_ignores_symbol_field(client: TestClient) -> None:
    """Symbol is read-only after creation (FR-3.1.4) — bodies shouldn't be able to rename."""
    client.post("/api/stocks", json={"symbol": "AAPL", "currency": "USD"})

    response = client.patch(
        "/api/stocks/AAPL",
        json={"symbol": "MSFT", "notes": "tagged"},
    )
    assert response.status_code == 200
    assert response.json()["symbol"] == "AAPL"
    # And MSFT was not created as a side effect.
    assert client.get("/api/stocks/MSFT").status_code == 404


def test_units_note_round_trips_via_create_and_patch(client: TestClient) -> None:
    create = client.post(
        "/api/stocks",
        json={
            "symbol": "AAPL",
            "currency": "USD",
            "units_note": "Millions of US $",
        },
    )
    assert create.status_code == 201
    assert create.json()["units_note"] == "Millions of US $"

    patched = client.patch(
        "/api/stocks/AAPL",
        json={"units_note": "Quarterly Data | Millions of US $ except per share data"},
    )
    assert patched.status_code == 200
    assert (
        patched.json()["units_note"]
        == "Quarterly Data | Millions of US $ except per share data"
    )

    fetched = client.get("/api/stocks/AAPL").json()
    assert fetched["units_note"] == (
        "Quarterly Data | Millions of US $ except per share data"
    )


def test_patch_stock_unknown_symbol_returns_404(client: TestClient) -> None:
    response = client.patch("/api/stocks/NOPE", json={"notes": "x"})
    assert response.status_code == 404
