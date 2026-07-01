"""Registry of valuation models — runs them all and summarises the results."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from app.services.valuations import ev_ebit, ev_ebitda, ev_fcf, pb_based, pe_based
from app.services.valuations._helpers import median_decimal
from app.services.valuations.types import ValuationInputs, ValuationResult

MODELS: dict[str, Callable[[ValuationInputs], ValuationResult]] = {
    pe_based.MODEL_NAME: pe_based.compute,
    pb_based.MODEL_NAME: pb_based.compute,
    ev_ebitda.MODEL_NAME: ev_ebitda.compute,
    ev_ebit.MODEL_NAME: ev_ebit.compute,
    ev_fcf.MODEL_NAME: ev_fcf.compute,
}


def run_all(inputs: ValuationInputs) -> dict[str, ValuationResult]:
    """Run every registered model and return their results keyed by model name."""
    return {name: model(inputs) for name, model in MODELS.items()}


def summarize(
    results: dict[str, ValuationResult], current_price: Decimal | None
) -> dict[str, Any]:
    """Aggregate the computable fair values into average/median/upside.

    `upside_pct` is the percentage gap between the average fair value and
    the current price (positive = undervalued, negative = overvalued).
    """
    fair_values = [
        r.fair_value
        for r in results.values()
        if r.computable and r.fair_value is not None
    ]
    if not fair_values:
        return {
            "average": None,
            "median": None,
            "current_price": current_price,
            "upside_pct": None,
        }

    average = sum(fair_values, start=Decimal(0)) / Decimal(len(fair_values))
    median_value = median_decimal(fair_values)
    upside_pct: Decimal | None = None
    if current_price is not None and current_price > 0:
        upside_pct = (average - current_price) / current_price * Decimal(100)

    return {
        "average": average,
        "median": median_value,
        "current_price": current_price,
        "upside_pct": upside_pct,
    }
