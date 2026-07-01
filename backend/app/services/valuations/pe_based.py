"""P/E-based valuation — fair price = TTM EPS × target P/E."""

from __future__ import annotations

from app.services.valuations._helpers import get_param, ttm_sum
from app.services.valuations.types import ValuationInputs, ValuationResult, step

MODEL_NAME = "pe_based"


def compute(inputs: ValuationInputs) -> ValuationResult:
    target_pe = get_param(inputs.parameters, "target_pe")
    if target_pe is None or target_pe <= 0:
        return ValuationResult(
            model=MODEL_NAME,
            fair_value=None,
            computable=False,
            reason="P/E valuation needs a positive target_pe.",
        )

    ttm_eps = ttm_sum(inputs.quarters, "eps_diluted")
    if ttm_eps is None:
        return ValuationResult(
            model=MODEL_NAME,
            fair_value=None,
            computable=False,
            reason="P/E valuation needs a full trailing-twelve-months of EPS.",
        )
    if ttm_eps <= 0:
        return ValuationResult(
            model=MODEL_NAME,
            fair_value=None,
            computable=False,
            reason="P/E valuation undefined for non-positive earnings.",
        )

    fair_value = ttm_eps * target_pe
    steps = [
        step("TTM EPS (diluted)", ttm_eps),
        step("Target P/E", target_pe, fmt="ratio"),
        step("Fair value per share", fair_value, formula="EPS × target P/E"),
    ]
    return ValuationResult(
        model=MODEL_NAME,
        fair_value=fair_value,
        computable=True,
        inputs={"ttm_eps": ttm_eps, "target_pe": target_pe},
        steps=steps,
    )
