"""Threshold-driven scorer — maps a raw metric value to a 0–100 score.

Threshold table format (one entry per metric, from `settings.grade_thresholds`):

    {
      "direction": "higher_better" | "lower_better",
      "ranges": [[boundary, score], ...]   # walked top-to-bottom; first match wins
    }

A `None` boundary is the catch-all (used as the last entry).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def _to_decimal(raw: Any) -> Decimal:
    return raw if isinstance(raw, Decimal) else Decimal(str(raw))


def score_metric(value: Decimal, threshold: dict[str, Any]) -> int | None:
    """Return the score for `value` against the given threshold table.

    Returns None if `threshold` is empty or malformed; that bubbles up to
    the aggregator, which will exclude this metric from the sub-grade.
    """
    direction = threshold.get("direction")
    ranges = threshold.get("ranges") or []

    for entry in ranges:
        boundary, score = entry[0], entry[1]
        if boundary is None:
            return int(score)
        boundary_dec = _to_decimal(boundary)
        if direction == "higher_better" and value >= boundary_dec:
            return int(score)
        if direction == "lower_better" and value <= boundary_dec:
            return int(score)

    return None
