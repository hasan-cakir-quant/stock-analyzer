"""P/B-based valuation — fair price = target P/B × book value per share.

Book value is the latest reported total equity; per-share uses the same
diluted share count as the other models. Applicable to all stocks, including
banks/financials (where EV-based models don't apply).
"""

from __future__ import annotations

from app.services.valuations._helpers import get_param, latest
from app.services.valuations.types import ValuationInputs, ValuationResult, step

MODEL_NAME = "pb_based"


def compute(inputs: ValuationInputs) -> ValuationResult:
    target_pb = get_param(inputs.parameters, "target_pb")
    if target_pb is None or target_pb <= 0:
        return ValuationResult(
            model=MODEL_NAME,
            fair_value=None,
            computable=False,
            reason="P/B valuation needs a positive target_pb.",
        )

    book_value = latest(inputs.quarters, "total_equity")
    if book_value is None:
        return ValuationResult(
            model=MODEL_NAME,
            fair_value=None,
            computable=False,
            reason="P/B valuation needs reported total equity (book value).",
        )
    if book_value <= 0:
        return ValuationResult(
            model=MODEL_NAME,
            fair_value=None,
            computable=False,
            reason="P/B valuation undefined for non-positive book value.",
        )

    if inputs.shares_outstanding is None or inputs.shares_outstanding <= 0:
        return ValuationResult(
            model=MODEL_NAME,
            fair_value=None,
            computable=False,
            reason="shares_outstanding required to derive per-share fair value.",
        )

    book_value_per_share = book_value / inputs.shares_outstanding
    fair_value = target_pb * book_value_per_share

    steps = [
        step("Book value (total equity)", book_value),
        step("Shares outstanding", inputs.shares_outstanding),
        step(
            "Book value per share",
            book_value_per_share,
            formula="Total equity / shares",
        ),
        step("Target P/B", target_pb, fmt="ratio"),
        step(
            "Fair value per share",
            fair_value,
            formula="BVPS × target P/B",
        ),
    ]
    return ValuationResult(
        model=MODEL_NAME,
        fair_value=fair_value,
        computable=True,
        inputs={
            "book_value": book_value,
            "book_value_per_share": book_value_per_share,
            "target_pb": target_pb,
            "shares_outstanding": inputs.shares_outstanding,
        },
        steps=steps,
    )
