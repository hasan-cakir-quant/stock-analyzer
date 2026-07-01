"""Value types shared by every valuation model.

Models take a `ValuationInputs` and return a `ValuationResult`. We use a
plain `Quarter` dataclass rather than the SQLAlchemy `QuarterlyFinancial`
so the valuation layer stays free of DB types and trivially testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(slots=True)
class Quarter:
    """One reporting period — every line item the valuation models can read."""

    period: str  # e.g. "2024-Q3"

    # Income statement
    revenue: Decimal | None = None
    cogs: Decimal | None = None
    gross_profit: Decimal | None = None
    operating_income: Decimal | None = None
    interest_expense: Decimal | None = None
    net_income: Decimal | None = None
    eps_diluted: Decimal | None = None
    ebitda: Decimal | None = None
    shares_outstanding_diluted: Decimal | None = None

    # Balance sheet
    cash_and_equivalents: Decimal | None = None
    short_term_investments: Decimal | None = None
    total_current_assets: Decimal | None = None
    total_assets: Decimal | None = None
    short_term_debt: Decimal | None = None
    total_current_liabilities: Decimal | None = None
    long_term_debt: Decimal | None = None
    total_equity: Decimal | None = None
    inventory: Decimal | None = None
    receivables: Decimal | None = None

    # Cash flow
    operating_cash_flow: Decimal | None = None
    capex: Decimal | None = None
    free_cash_flow: Decimal | None = None
    dividends_paid: Decimal | None = None

    # Market data
    closing_price: Decimal | None = None


@dataclass(slots=True)
class ValuationInputs:
    """Everything a valuation model might need.

    `quarters` is sorted ascending by period (oldest first). `parameters`
    is the merged Parameter Panel state (per-stock + global defaults) as
    returned by `GET /api/stocks/{symbol}/parameters`.
    """

    quarters: list[Quarter]
    parameters: dict[str, Any]
    shares_outstanding: Decimal | None
    current_price: Decimal | None
    # True for banks / financials, where the enterprise-value bridge
    # (deposits aren't debt, reserves aren't excess cash) is meaningless —
    # EV-based models opt out and return not-computable.
    is_financial: bool = False


@dataclass(slots=True)
class ValuationResult:
    """One model's output.

    `inputs` records the slice of data we used so the snapshot/UI can show
    *why* this number came out the way it did. `steps` records the ordered
    intermediate calculations — the popover renders them as a worksheet so
    a reader can audit the math without re-running the model.
    """

    model: str
    fair_value: Decimal | None
    computable: bool
    reason: str | None = None
    inputs: dict[str, Any] = field(default_factory=dict)
    steps: list[dict[str, Any]] = field(default_factory=list)


def step(
    label: str,
    value: Decimal | None,
    *,
    formula: str | None = None,
    fmt: str = "currency",
    details: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build one row for the `steps` worksheet.

    `fmt` is a hint for the UI: "currency", "percent", "percent_pct",
    "ratio", "integer", or "number".

    `details` is an optional list of sub-rows, each shaped like
    `{label, value, format}`. The UI renders them indented under the
    parent step — useful for showing the four quarter values that
    compose a TTM total, etc.
    """
    return {
        "label": label,
        "value": value,
        "formula": formula,
        "format": fmt,
        "details": details,
    }
