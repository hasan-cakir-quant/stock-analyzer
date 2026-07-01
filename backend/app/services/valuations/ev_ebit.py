"""EV/EBIT multiple — fair EV = TTM EBIT × target multiple, then bridge to equity.

EBIT is taken as operating income (the standard proxy; EBITDA = EBIT + D&A).
"""

from __future__ import annotations

from decimal import Decimal

from app.services.valuations._helpers import get_param, latest, ttm_sum
from app.services.valuations.types import ValuationInputs, ValuationResult, step

MODEL_NAME = "ev_ebit"


def compute(inputs: ValuationInputs) -> ValuationResult:
    if inputs.is_financial:
        return ValuationResult(
            model=MODEL_NAME,
            fair_value=None,
            computable=False,
            reason="Not applicable to financials — use P/E or P/B.",
        )

    target_multiple = get_param(inputs.parameters, "target_ev_ebit")
    if target_multiple is None or target_multiple <= 0:
        return ValuationResult(
            model=MODEL_NAME,
            fair_value=None,
            computable=False,
            reason="EV/EBIT needs a positive target_ev_ebit multiple.",
        )

    ttm_ebit = ttm_sum(inputs.quarters, "operating_income")
    if ttm_ebit is None:
        return ValuationResult(
            model=MODEL_NAME,
            fair_value=None,
            computable=False,
            reason="EV/EBIT needs a full trailing-twelve-months of EBIT.",
        )
    if ttm_ebit <= 0:
        return ValuationResult(
            model=MODEL_NAME,
            fair_value=None,
            computable=False,
            reason="EV/EBIT undefined for non-positive EBIT.",
        )

    if inputs.shares_outstanding is None or inputs.shares_outstanding <= 0:
        return ValuationResult(
            model=MODEL_NAME,
            fair_value=None,
            computable=False,
            reason="shares_outstanding required to derive per-share fair value.",
        )

    long_term_debt = latest(inputs.quarters, "long_term_debt") or Decimal(0)
    short_term_debt = latest(inputs.quarters, "short_term_debt") or Decimal(0)
    cash = latest(inputs.quarters, "cash_and_equivalents") or Decimal(0)
    net_debt = long_term_debt + short_term_debt - cash

    fair_ev = ttm_ebit * target_multiple
    fair_equity = fair_ev - net_debt
    fair_value = fair_equity / inputs.shares_outstanding

    steps = [
        step("TTM EBIT", ttm_ebit, formula="Σ last 4 quarters of operating income"),
        step("Target EV/EBIT multiple", target_multiple, fmt="ratio"),
        step(
            "Fair enterprise value",
            fair_ev,
            formula="TTM EBIT × target multiple",
        ),
        step("Long-term debt (latest)", long_term_debt),
        step("Short-term debt (latest)", short_term_debt),
        step("Cash & equivalents (latest)", cash),
        step("Net debt", net_debt, formula="LT debt + ST debt − cash"),
        step("Fair equity value", fair_equity, formula="Fair EV − net debt"),
        step("Shares outstanding", inputs.shares_outstanding),
        step(
            "Fair value per share",
            fair_value,
            formula="Fair equity / shares",
        ),
    ]

    return ValuationResult(
        model=MODEL_NAME,
        fair_value=fair_value,
        computable=True,
        inputs={
            "ttm_ebit": ttm_ebit,
            "target_ev_ebit": target_multiple,
            "net_debt": net_debt,
            "shares_outstanding": inputs.shares_outstanding,
        },
        steps=steps,
    )
