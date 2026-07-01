"""Unit tests for the two valuation models and the registry summary.

Each model has a happy-path case with hand-computed expected values and
at least one "not computable" case proving the right reason is returned.
"""

from __future__ import annotations

from decimal import Decimal

from app.services.valuations import Quarter, ValuationInputs, run_all, summarize
from app.services.valuations import ev_ebit, ev_ebitda, ev_fcf, pb_based, pe_based
from app.services.valuations.types import ValuationResult


def _q(period: str, **fields) -> Quarter:
    return Quarter(period=period, **fields)


def _approx(value: Decimal | None, expected: float, tol: float = 1e-3) -> bool:
    """Loose equality for hand-computed expected values."""
    return value is not None and abs(float(value) - expected) < tol


# --- P/E Based ---------------------------------------------------------


def test_pe_based_simple() -> None:
    """TTM EPS=4, target P/E=20 → V = 80."""
    quarters = [_q(f"2024-Q{i + 1}", eps_diluted=Decimal("1")) for i in range(4)]
    inputs = ValuationInputs(
        quarters=quarters,
        parameters={"target_pe": "20"},
        shares_outstanding=Decimal("50"),
        current_price=None,
    )
    result = pe_based.compute(inputs)
    assert result.computable
    assert _approx(result.fair_value, 80.0, tol=1e-6)


def test_pe_based_needs_target_pe() -> None:
    quarters = [_q(f"2024-Q{i + 1}", eps_diluted=Decimal("1")) for i in range(4)]
    inputs = ValuationInputs(
        quarters=quarters,
        parameters={"target_pe": None},
        shares_outstanding=Decimal("50"),
        current_price=None,
    )
    result = pe_based.compute(inputs)
    assert not result.computable
    assert "target_pe" in result.reason


# --- EV/EBITDA ---------------------------------------------------------


def test_ev_ebitda_bridges_to_equity() -> None:
    """TTM EBITDA=200, target=10 → fair_ev=2000.
    Net debt = (LTD 100 + STD 50) - Cash 30 = 120.
    Fair equity = 1880; shares=50 → 37.6.
    """
    quarters = [
        _q(
            f"2024-Q{i + 1}",
            ebitda=Decimal("50"),
            long_term_debt=Decimal("100"),
            short_term_debt=Decimal("50"),
            cash_and_equivalents=Decimal("30"),
        )
        for i in range(4)
    ]
    inputs = ValuationInputs(
        quarters=quarters,
        parameters={"target_ev_ebitda": "10"},
        shares_outstanding=Decimal("50"),
        current_price=None,
    )
    result = ev_ebitda.compute(inputs)
    assert result.computable, result.reason
    assert _approx(result.fair_value, 37.6, tol=1e-6)


def test_ev_ebitda_returns_not_computable_with_negative_ebitda() -> None:
    quarters = [_q(f"2024-Q{i + 1}", ebitda=Decimal("-10")) for i in range(4)]
    inputs = ValuationInputs(
        quarters=quarters,
        parameters={"target_ev_ebitda": "10"},
        shares_outstanding=Decimal("50"),
        current_price=None,
    )
    result = ev_ebitda.compute(inputs)
    assert not result.computable
    assert "EBITDA" in result.reason


# --- P/B Based ---------------------------------------------------------


def test_pb_based_uses_book_value_per_share() -> None:
    """Latest total equity = 500, shares = 50 → BVPS = 10.
    target P/B = 1.5 → fair value = 15.
    """
    quarters = [
        _q(f"2024-Q{i + 1}", total_equity=Decimal("500")) for i in range(4)
    ]
    inputs = ValuationInputs(
        quarters=quarters,
        parameters={"target_pb": "1.5"},
        shares_outstanding=Decimal("50"),
        current_price=None,
    )
    result = pb_based.compute(inputs)
    assert result.computable, result.reason
    assert _approx(result.fair_value, 15.0, tol=1e-6)


def test_pb_based_needs_target_pb() -> None:
    quarters = [_q(f"2024-Q{i + 1}", total_equity=Decimal("500")) for i in range(4)]
    inputs = ValuationInputs(
        quarters=quarters,
        parameters={"target_pb": None},
        shares_outstanding=Decimal("50"),
        current_price=None,
    )
    result = pb_based.compute(inputs)
    assert not result.computable
    assert "target_pb" in result.reason


# --- EV/FCF ------------------------------------------------------------


def test_ev_fcf_bridges_to_equity() -> None:
    """TTM FCF=200, target=10 → fair_ev=2000.
    Net debt = (LTD 100 + STD 50) - Cash 30 = 120.
    Fair equity = 1880; shares=50 → 37.6.
    """
    quarters = [
        _q(
            f"2024-Q{i + 1}",
            free_cash_flow=Decimal("50"),
            long_term_debt=Decimal("100"),
            short_term_debt=Decimal("50"),
            cash_and_equivalents=Decimal("30"),
        )
        for i in range(4)
    ]
    inputs = ValuationInputs(
        quarters=quarters,
        parameters={"target_ev_fcf": "10"},
        shares_outstanding=Decimal("50"),
        current_price=None,
    )
    result = ev_fcf.compute(inputs)
    assert result.computable, result.reason
    assert _approx(result.fair_value, 37.6, tol=1e-6)


def test_ev_fcf_returns_not_computable_with_negative_fcf() -> None:
    quarters = [_q(f"2024-Q{i + 1}", free_cash_flow=Decimal("-10")) for i in range(4)]
    inputs = ValuationInputs(
        quarters=quarters,
        parameters={"target_ev_fcf": "10"},
        shares_outstanding=Decimal("50"),
        current_price=None,
    )
    result = ev_fcf.compute(inputs)
    assert not result.computable
    assert "free cash flow" in (result.reason or "").lower()


# --- Financials opt out of EV models -----------------------------------


def test_ev_models_not_computable_for_financials() -> None:
    quarters = [
        _q(
            f"2024-Q{i + 1}",
            ebitda=Decimal("50"),
            operating_income=Decimal("40"),
            free_cash_flow=Decimal("30"),
        )
        for i in range(4)
    ]
    inputs = ValuationInputs(
        quarters=quarters,
        parameters={
            "target_ev_ebitda": "10",
            "target_ev_ebit": "12",
            "target_ev_fcf": "10",
        },
        shares_outstanding=Decimal("50"),
        current_price=None,
        is_financial=True,
    )
    for model in (ev_ebitda, ev_ebit, ev_fcf):
        result = model.compute(inputs)
        assert not result.computable
        assert "financials" in (result.reason or "").lower()


# --- EV/EBIT -----------------------------------------------------------


def test_ev_ebit_bridges_to_equity() -> None:
    """TTM EBIT=200, target=10 → fair_ev=2000.
    Net debt = (LTD 100 + STD 50) - Cash 30 = 120.
    Fair equity = 1880; shares=50 → 37.6.
    """
    quarters = [
        _q(
            f"2024-Q{i + 1}",
            operating_income=Decimal("50"),
            long_term_debt=Decimal("100"),
            short_term_debt=Decimal("50"),
            cash_and_equivalents=Decimal("30"),
        )
        for i in range(4)
    ]
    inputs = ValuationInputs(
        quarters=quarters,
        parameters={"target_ev_ebit": "10"},
        shares_outstanding=Decimal("50"),
        current_price=None,
    )
    result = ev_ebit.compute(inputs)
    assert result.computable, result.reason
    assert _approx(result.fair_value, 37.6, tol=1e-6)


def test_ev_ebit_returns_not_computable_with_negative_ebit() -> None:
    quarters = [_q(f"2024-Q{i + 1}", operating_income=Decimal("-10")) for i in range(4)]
    inputs = ValuationInputs(
        quarters=quarters,
        parameters={"target_ev_ebit": "10"},
        shares_outstanding=Decimal("50"),
        current_price=None,
    )
    result = ev_ebit.compute(inputs)
    assert not result.computable
    assert "EBIT" in result.reason


# --- Registry / summary ------------------------------------------------


def test_run_all_returns_a_result_for_every_registered_model() -> None:
    inputs = ValuationInputs(
        quarters=[], parameters={}, shares_outstanding=None, current_price=None
    )
    results = run_all(inputs)
    assert set(results.keys()) == {
        "pe_based",
        "pb_based",
        "ev_ebitda",
        "ev_ebit",
        "ev_fcf",
    }
    # Every one of them should report not-computable with empty inputs.
    for name, r in results.items():
        assert not r.computable, f"{name} unexpectedly computable on empty inputs"
        assert r.reason, f"{name} missing reason"


def test_summarize_aggregates_only_computable_results() -> None:
    results = {
        "a": ValuationResult("a", Decimal("100"), True),
        "b": ValuationResult("b", Decimal("120"), True),
        "c": ValuationResult("c", None, False, reason="missing"),
    }
    summary = summarize(results, current_price=Decimal("100"))
    assert summary["average"] == Decimal("110")
    assert summary["median"] == Decimal("110")
    assert summary["current_price"] == Decimal("100")
    # (110 - 100) / 100 * 100 = 10% upside
    assert _approx(summary["upside_pct"], 10.0, tol=1e-6)


def test_summarize_with_no_computable_results_returns_nones() -> None:
    results = {"a": ValuationResult("a", None, False, reason="x")}
    summary = summarize(results, current_price=Decimal("50"))
    assert summary == {
        "average": None,
        "median": None,
        "current_price": Decimal("50"),
        "upside_pct": None,
    }


def test_summarize_handles_missing_current_price() -> None:
    results = {"a": ValuationResult("a", Decimal("80"), True)}
    summary = summarize(results, current_price=None)
    assert summary["average"] == Decimal("80")
    assert summary["upside_pct"] is None
