"""Tests for the settings endpoints."""

from __future__ import annotations

from copy import deepcopy

from fastapi.testclient import TestClient


def _valid_payload(seed: dict) -> dict:
    """Round-trip the seeded GET payload, stripping the read-only fields."""
    payload = deepcopy(seed)
    payload.pop("id", None)
    payload.pop("updated_at", None)
    return payload


def test_get_settings_returns_seeded_singleton(client: TestClient) -> None:
    response = client.get("/api/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 1
    assert set(body["general_grade_weights"].keys()) == {
        "profitability",
        "valuation",
        "financial_strength",
        "growth",
        "efficiency",
        "safety",
        "dividend",
    }
    assert set(body["sub_grade_weights"].keys()) == set(body["general_grade_weights"].keys())
    assert body["currency_format"]["decimal_places"] == 2


def test_put_settings_round_trip(client: TestClient) -> None:
    seed = client.get("/api/settings").json()
    payload = _valid_payload(seed)

    # Mutate something on each side of the schema to prove a true round-trip.
    payload["general_grade_weights"]["profitability"] = "25"
    payload["general_grade_weights"]["valuation"] = "15"
    payload["sub_grade_weights"]["profitability"]["roe"] = "30"
    payload["sub_grade_weights"]["profitability"]["roa"] = "5"
    payload["currency_format"]["decimal_places"] = 4
    payload["global_market_assumptions"]["target_pe"] = "22"

    put_response = client.put("/api/settings", json=payload)
    assert put_response.status_code == 200, put_response.text
    put_body = put_response.json()
    assert put_body["general_grade_weights"]["profitability"] == "25"
    assert put_body["currency_format"]["decimal_places"] == 4
    assert put_body["global_market_assumptions"]["target_pe"] == "22"

    refetch = client.get("/api/settings").json()
    assert refetch["general_grade_weights"]["profitability"] == "25"
    assert refetch["sub_grade_weights"]["profitability"]["roe"] == "30"


def test_put_settings_rejects_general_weights_not_summing_to_100(
    client: TestClient,
) -> None:
    payload = _valid_payload(client.get("/api/settings").json())
    # 25 + 20 + 15 + 15 + 10 + 10 + 10 = 105
    payload["general_grade_weights"]["profitability"] = "25"

    response = client.put("/api/settings", json=payload)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(
        "General grade weights must sum to 100" in str(err.get("msg", "")) for err in detail
    ), detail


def test_put_settings_rejects_sub_grade_weights_not_summing_to_100(
    client: TestClient,
) -> None:
    payload = _valid_payload(client.get("/api/settings").json())
    # Make profitability's internal weights sum to 105 (was 100).
    payload["sub_grade_weights"]["profitability"]["roe"] = "25"

    response = client.put("/api/settings", json=payload)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(
        "Sub-grade 'profitability' internal weights must sum to 100" in str(err.get("msg", ""))
        for err in detail
    ), detail
