"""Shared numeric / period helpers used across statement parsers."""

from __future__ import annotations

from datetime import date
from decimal import Decimal


def _format_decimal(d: Decimal) -> str:
    """Render a Decimal as a clean fixed-point string with no trailing zeros."""
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"


def _quarter_for(period_end: date) -> str:
    """Calendar quarter the reporting period mostly covers (midpoint rule)."""
    middle_month = period_end.month - 1
    middle_year = period_end.year
    if middle_month == 0:
        middle_month = 12
        middle_year -= 1
    quarter = (middle_month - 1) // 3 + 1
    return f"{middle_year}-Q{quarter}"
