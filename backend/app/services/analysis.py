"""Run-Full-Analysis orchestrator.

Stitches Tasks 8 / 9 / 10 together: valuations → grades (which need the
average fair value from valuations) → growth. Returns one combined payload
in the JSONB shape that snapshots will eventually freeze.

This module is pure — it doesn't touch the DB or HTTP. The router loads
the data and hands it in.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.db.models import QuarterlyFinancial
from app.services.grading import GradingInputs, compute_grades, to_payload as grades_payload
from app.services.growth import GrowthInputs, compute_growth, to_payload as growth_payload
from app.services.valuations import Quarter, ValuationInputs, run_all, summarize
from app.services.valuations._helpers import latest_shares_outstanding


def to_quarter(row: QuarterlyFinancial) -> Quarter:
    """Adapt the ORM row to the value-type the service layer consumes."""
    return Quarter(
        period=row.period,
        revenue=row.revenue,
        cogs=row.cogs,
        gross_profit=row.gross_profit,
        operating_income=row.operating_income,
        interest_expense=row.interest_expense,
        net_income=row.net_income,
        eps_diluted=row.eps_diluted,
        ebitda=row.ebitda,
        shares_outstanding_diluted=row.shares_outstanding_diluted,
        cash_and_equivalents=row.cash_and_equivalents,
        short_term_investments=row.short_term_investments,
        total_current_assets=row.total_current_assets,
        total_assets=row.total_assets,
        short_term_debt=row.short_term_debt,
        total_current_liabilities=row.total_current_liabilities,
        long_term_debt=row.long_term_debt,
        total_equity=row.total_equity,
        inventory=row.inventory,
        receivables=row.receivables,
        operating_cash_flow=row.operating_cash_flow,
        capex=row.capex,
        free_cash_flow=row.free_cash_flow,
        dividends_paid=row.dividends_paid,
        closing_price=row.closing_price,
    )


def _serialize_valuations(results: dict, summary: dict) -> dict[str, Any]:
    return {
        "models": {
            name: {
                "fair_value": _maybe_float(r.fair_value),
                "computable": r.computable,
                "reason": r.reason,
                "inputs": _serialize_inputs(r.inputs),
                "steps": [_serialize_step(s) for s in r.steps],
            }
            for name, r in results.items()
        },
        "summary": {
            "average": _maybe_float(summary["average"]),
            "median": _maybe_float(summary["median"]),
            "current_price": _maybe_float(summary["current_price"]),
            "upside_pct": _maybe_float(summary["upside_pct"]),
        },
    }


def _serialize_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    return {
        k: (_maybe_float(v) if isinstance(v, Decimal) else v) for k, v in inputs.items()
    }


def _serialize_step(step: dict[str, Any]) -> dict[str, Any]:
    raw_details = step.get("details")
    details = (
        [
            {
                "label": d.get("label"),
                "value": _maybe_float(d.get("value")),
                "format": d.get("format", "currency"),
            }
            for d in raw_details
        ]
        if raw_details
        else None
    )
    return {
        "label": step.get("label"),
        "value": _maybe_float(step.get("value")),
        "formula": step.get("formula"),
        "format": step.get("format", "currency"),
        "details": details,
    }


def _maybe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return value


def run_full_analysis(
    *,
    symbol: str,
    quarters: list[Quarter],
    parameters: dict[str, Any],
    shares_outstanding: Decimal | None,
    current_price: Decimal | None,
    settings_general_grade_weights: dict[str, Decimal],
    settings_sub_grade_weights: dict[str, dict[str, Decimal]],
    settings_grade_thresholds: dict[str, dict[str, Any]],
    is_financial: bool = False,
) -> dict[str, Any]:
    """Run the three engines in order and return the combined payload."""
    # Prefer the diluted share count off the most recent quarterly
    # income statement — that's the per-share basis used for diluted
    # EPS, which keeps fair-value math aligned with the EPS we report.
    # Fall back to the stock-metadata value if the income statement
    # doesn't carry one (older imports, or freshly added stocks).
    shares_for_calc = latest_shares_outstanding(quarters) or shares_outstanding

    # 1. Valuations — compute first because grading uses the average fair value.
    valuation_inputs = ValuationInputs(
        quarters=quarters,
        parameters=parameters,
        shares_outstanding=shares_for_calc,
        current_price=current_price,
        is_financial=is_financial,
    )
    valuation_results = run_all(valuation_inputs)
    valuation_summary = summarize(valuation_results, current_price)

    # 2. Grades — feed the average fair value through.
    grading_inputs = GradingInputs(
        quarters=quarters,
        parameters=parameters,
        shares_outstanding=shares_for_calc,
        current_price=current_price,
        average_fair_value=valuation_summary["average"],
        general_grade_weights=settings_general_grade_weights,
        sub_grade_weights=settings_sub_grade_weights,
        grade_thresholds=settings_grade_thresholds,
    )
    grades_result = compute_grades(grading_inputs)

    # 3. Growth metrics.
    growth_result = compute_growth(GrowthInputs(quarters=quarters))

    return {
        "symbol": symbol,
        "current_price": _maybe_float(current_price),
        "valuations": _serialize_valuations(valuation_results, valuation_summary),
        "grades": grades_payload(grades_result),
        "growth": growth_payload(growth_result),
    }
