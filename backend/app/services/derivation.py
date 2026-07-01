"""Derivation rules for quarterly line items (FR-3.2.4).

Whenever the persisted row leaves a derivable field null but the inputs
are present, fill it in. A user-supplied value (even one held over from a
previous PUT) is always preserved — derivation only fills nulls.

EPS uses the per-quarter diluted share count when available, falling back
to the stock-level shares_outstanding so users don't need to re-enter the
share count every quarter. The fallback approximates with current shares;
users who care about precise historical EPS can enter the per-quarter
diluted shares explicitly and the override sticks.
"""

from __future__ import annotations

from decimal import Decimal

from app.db.models import QuarterlyFinancial


def apply_derivations(
    row: QuarterlyFinancial, *, stock_shares_outstanding: Decimal | None = None
) -> None:
    """Mutate `row` in place, populating nullable derived fields where possible."""
    if (
        row.gross_profit is None
        and row.revenue is not None
        and row.cogs is not None
    ):
        row.gross_profit = row.revenue - row.cogs

    if (
        row.free_cash_flow is None
        and row.operating_cash_flow is not None
        and row.capex is not None
    ):
        row.free_cash_flow = row.operating_cash_flow - row.capex

    # EPS (diluted) — prefer the per-quarter diluted share count; fall back
    # to the stock-level shares so users who entered shares once on the
    # stock metadata don't have to repeat it for every quarter.
    if row.eps_diluted is None and row.net_income is not None:
        shares = row.shares_outstanding_diluted or stock_shares_outstanding
        if shares is not None and shares > 0:
            row.eps_diluted = row.net_income / shares
