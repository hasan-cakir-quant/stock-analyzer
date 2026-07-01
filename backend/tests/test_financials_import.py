"""Tests for the financial-statement import flow.

Covers the SEC EDGAR companyfacts parser end-to-end and the two endpoints
(`/import-preview` + `/bulk-upsert`). The parser fixture is a small XBRL
companyfacts payload — minimal, but enough to exercise the flow/instant
bucketing, quarter mapping, and the bulk-upsert + derivation pipeline.
"""

from __future__ import annotations

import json
from datetime import date
from io import BytesIO

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# SEC EDGAR companyfacts fixture
# ---------------------------------------------------------------------------


def _companyfacts_fixture() -> dict:
    """Two quarters (2024-Q1, 2024-Q2) of revenue, net income, and total
    assets, shaped like SEC's XBRL companyfacts JSON. Flow facts carry a
    (start, end) window; instant facts carry only `end`."""

    def flow(start: str, end: str, val: float) -> dict:
        return {"start": start, "end": end, "val": val, "form": "10-Q", "filed": end}

    def instant(end: str, val: float) -> dict:
        return {"end": end, "val": val, "form": "10-Q", "filed": end}

    return {
        "cik": 320193,
        "entityName": "FIXTURE INC",
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            flow("2024-01-01", "2024-03-31", 1000),
                            flow("2024-04-01", "2024-06-30", 1100),
                        ]
                    }
                },
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            flow("2024-01-01", "2024-03-31", 100),
                            flow("2024-04-01", "2024-06-30", 110),
                        ]
                    }
                },
                "Assets": {
                    "units": {
                        "USD": [
                            instant("2024-03-31", 5000),
                            instant("2024-06-30", 5200),
                        ]
                    }
                },
            }
        },
    }


def _companyfacts_text() -> str:
    return json.dumps(_companyfacts_fixture())


# ---------- pure parser ---------------------------------------------------


def test_sec_edgar_parser_returns_expected_preview() -> None:
    from app.services.imports.sec_edgar_all import parse

    preview = parse(_companyfacts_text())

    assert preview.parser_id == "sec_edgar_all"
    assert preview.source == "sec_edgar"
    assert preview.statement == "all"
    assert preview.caption  # default caption stamped on

    # Two flow quarters, mapped via the midpoint rule.
    assert [r.period for r in preview.rows] == ["2024-Q1", "2024-Q2"]

    by_period = {r.period: r for r in preview.rows}
    q1 = by_period["2024-Q1"]
    assert q1.period_end_date == date(2024, 3, 31)
    # EDGAR ships absolute USD already — values pass through unscaled.
    assert q1.fields["revenue"] == "1000"
    assert q1.fields["net_income"] == "100"
    assert q1.fields["total_assets"] == "5000"

    q2 = by_period["2024-Q2"]
    assert q2.period_end_date == date(2024, 6, 30)
    assert q2.fields["revenue"] == "1100"
    assert q2.fields["total_assets"] == "5200"


def test_quarter_mapping_handles_fiscal_shifted_year_end_dates() -> None:
    """Salesforce-style FY (ending Jan 31). Period-end dates fall on
    Apr 30 / Jul 31 / Oct 31 / Jan 31 and should land in Q1/Q2/Q3/Q4
    of the surrounding calendar year via the midpoint rule."""
    from app.services.imports._numeric import _quarter_for

    assert _quarter_for(date(2011, 4, 30)) == "2011-Q1"
    assert _quarter_for(date(2011, 7, 31)) == "2011-Q2"
    assert _quarter_for(date(2011, 10, 31)) == "2011-Q3"
    assert _quarter_for(date(2012, 1, 31)) == "2011-Q4"

    # Calendar-FY companies still resolve correctly.
    assert _quarter_for(date(2024, 3, 31)) == "2024-Q1"
    assert _quarter_for(date(2024, 6, 30)) == "2024-Q2"
    assert _quarter_for(date(2024, 9, 30)) == "2024-Q3"
    assert _quarter_for(date(2024, 12, 31)) == "2024-Q4"


def test_parser_rejects_invalid_json() -> None:
    from app.services.imports.sec_edgar_all import parse

    try:
        parse("this is not json")
    except ValueError as exc:
        assert "Not valid JSON" in str(exc)
    else:
        raise AssertionError("expected ValueError for invalid JSON")


def test_parser_rejects_non_object_root() -> None:
    from app.services.imports.sec_edgar_all import parse

    try:
        parse("[1, 2, 3]")
    except ValueError as exc:
        assert "object" in str(exc).lower()
    else:
        raise AssertionError("expected ValueError for non-object JSON")


# ---------- source registry -----------------------------------------------


def test_list_sources_exposes_only_sec_edgar(client: TestClient) -> None:
    response = client.get("/api/imports/sources")
    assert response.status_code == 200
    sources = response.json()
    ids = {s["id"] for s in sources}

    assert "sec_edgar_all" in ids
    # The removed scrapers must not be advertised.
    assert not any("macrotrends" in i for i in ids)
    assert not any("fintables" in i for i in ids)

    by_id = {s["id"]: s for s in sources}
    assert by_id["sec_edgar_all"]["statement"] == "all"
    assert by_id["sec_edgar_all"]["source"] == "sec_edgar"


# ---------- endpoint round-trip -------------------------------------------


def _create_aapl(client: TestClient) -> None:
    resp = client.post(
        "/api/stocks",
        json={"symbol": "AAPL", "currency": "USD", "shares_outstanding": "1000"},
    )
    assert resp.status_code == 201, resp.text


def test_import_preview_endpoint_returns_parsed_rows(client: TestClient) -> None:
    _create_aapl(client)

    payload_bytes = _companyfacts_text().encode("utf-8")
    response = client.post(
        "/api/stocks/AAPL/financials/import-preview",
        data={"parser_id": "sec_edgar_all"},
        files={"file": ("companyfacts.json", BytesIO(payload_bytes), "application/json")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["parser_id"] == "sec_edgar_all"
    assert [r["period"] for r in body["rows"]] == ["2024-Q1", "2024-Q2"]
    q1 = next(r for r in body["rows"] if r["period"] == "2024-Q1")
    assert q1["fields"]["revenue"] == "1000"
    assert q1["fields"]["total_assets"] == "5000"
    assert q1["period_end_date"] == "2024-03-31"


def test_import_preview_unknown_parser_returns_400(client: TestClient) -> None:
    _create_aapl(client)
    response = client.post(
        "/api/stocks/AAPL/financials/import-preview",
        data={"parser_id": "totally_made_up"},
        files={"file": ("x.json", BytesIO(b"{}"), "application/json")},
    )
    assert response.status_code == 400


def test_import_preview_unknown_stock_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/stocks/NOPE/financials/import-preview",
        data={"parser_id": "sec_edgar_all"},
        files={"file": ("x.json", BytesIO(b"{}"), "application/json")},
    )
    assert response.status_code == 404


def test_import_preview_invalid_json_returns_422(client: TestClient) -> None:
    _create_aapl(client)
    response = client.post(
        "/api/stocks/AAPL/financials/import-preview",
        data={"parser_id": "sec_edgar_all"},
        files={"file": ("x.json", BytesIO(b"not json at all"), "application/json")},
    )
    assert response.status_code == 422


# ---------- bulk upsert + derivations (parser-independent) ----------------


def test_bulk_upsert_persists_each_row_and_derives(client: TestClient) -> None:
    _create_aapl(client)
    payload = {
        "rows": [
            {
                "period": "2024-Q2",
                "period_end_date": "2024-06-30",
                "revenue": "900.000",
                "cogs": "360.000",
                "net_income": "80.000",
            },
            {
                "period": "2024-Q3",
                "period_end_date": "2024-09-30",
                "revenue": "1000.000",
                "cogs": "400.000",
                "net_income": "100.000",
            },
        ]
    }
    response = client.post("/api/stocks/AAPL/financials/bulk-upsert", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["written"] == 2
    assert sorted(body["periods"]) == ["2024-Q2", "2024-Q3"]

    listing = client.get("/api/stocks/AAPL/financials").json()
    by_period = {row["period"]: row for row in listing}
    assert by_period["2024-Q2"]["revenue"] == "900.000"
    assert by_period["2024-Q2"]["gross_profit"] == "540.000"  # derived
    assert by_period["2024-Q2"]["eps_diluted"] == "0.080"
    assert by_period["2024-Q2"]["period_end_date"] == "2024-06-30"
    assert by_period["2024-Q3"]["period_end_date"] == "2024-09-30"


def test_bulk_upsert_capex_feeds_into_fcf_derivation(client: TestClient) -> None:
    """free_cash_flow = operating_cash_flow − capex is derived server-side
    from the persisted (positive) capex on bulk upsert."""
    _create_aapl(client)
    payload = {
        "rows": [
            {
                "period": "2024-Q3",
                "period_end_date": "2024-09-30",
                "operating_cash_flow": "1983000000",
                "capex": "204000000",
            }
        ]
    }
    response = client.post("/api/stocks/AAPL/financials/bulk-upsert", json=payload)
    assert response.status_code == 200, response.text

    listing = client.get("/api/stocks/AAPL/financials").json()
    q3 = next(row for row in listing if row["period"] == "2024-Q3")
    assert q3["operating_cash_flow"] == "1983000000"
    assert q3["capex"] == "204000000"
    # 1,983,000,000 − 204,000,000 = 1,779,000,000.
    assert q3["free_cash_flow"] == "1779000000"


def test_bulk_upsert_archives_raw_payload_when_import_context_present(
    client: TestClient,
) -> None:
    _create_aapl(client)

    payload = {
        "import_context": {
            "parser_id": "sec_edgar_all",
            "source": "sec_edgar",
            "statement": "all",
            "caption": "Stored in absolute US$ (SEC EDGAR XBRL companyfacts)",
        },
        "rows": [
            {
                "period": "2024-Q1",
                "period_end_date": "2024-03-31",
                "revenue": "1000",
                "raw_source": {
                    "Revenues": "1000",
                    "NetIncomeLoss": "100",
                    "Assets": "5000",
                },
            },
        ],
    }
    response = client.post("/api/stocks/AAPL/financials/bulk-upsert", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["written"] == 1
    assert body["raw_payloads_archived"] == 1

    # The mapped field still landed in `quarterly_financials`.
    listing = client.get("/api/stocks/AAPL/financials").json()
    assert listing[0]["revenue"] == "1000"

    # Re-importing the same period replaces the archive in place
    # (single row keyed by stock+source+statement+period).
    payload["rows"][0]["raw_source"]["Revenues"] = "1100"
    second = client.post("/api/stocks/AAPL/financials/bulk-upsert", json=payload)
    assert second.status_code == 200
    assert second.json()["raw_payloads_archived"] == 1


def test_bulk_upsert_skips_archive_when_import_context_absent(
    client: TestClient,
) -> None:
    """Manual / scripted upserts that don't pass `import_context` should
    only touch `quarterly_financials` — the archive stays untouched even
    if the row carries `raw_source`."""
    _create_aapl(client)
    response = client.post(
        "/api/stocks/AAPL/financials/bulk-upsert",
        json={
            "rows": [
                {
                    "period": "2024-Q3",
                    "revenue": "1000000000",
                    "raw_source": {"Revenues": "1000"},
                },
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["raw_payloads_archived"] == 0


def test_bulk_upsert_invalid_period_returns_422(client: TestClient) -> None:
    _create_aapl(client)
    response = client.post(
        "/api/stocks/AAPL/financials/bulk-upsert",
        json={"rows": [{"period": "2024Q2", "revenue": "1"}]},
    )
    assert response.status_code == 422


def test_bulk_upsert_unknown_stock_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/stocks/UNKNOWN/financials/bulk-upsert",
        json={"rows": [{"period": "2024-Q1", "revenue": "1"}]},
    )
    assert response.status_code == 404
