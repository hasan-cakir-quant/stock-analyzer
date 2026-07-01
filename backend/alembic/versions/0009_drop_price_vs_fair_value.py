"""drop price_vs_fair_value from valuation sub-grade

Revision ID: 0009_drop_price_vs_fair_value
Revises: 0008_seed_dcf_templates
Create Date: 2026-05-21

Removes the `price_vs_fair_value` metric from the Valuation sub-grade.

Motivation: it was the only grading metric whose score depended on the
parameter set (via the average fair value from the eight valuation
models). When compare-mode runs multiple templates side-by-side every
other grade was identical across columns, but this single metric made
the Valuation grade — and therefore the General grade — drift per
column for no useful reason. Dropping it makes grade measurement a
property of the stock alone (financials + settings), so the Grades
panel can collapse to a single column.

What changes in the settings row:
1. `grade_thresholds.price_vs_fair_value` removed.
2. `sub_grade_weights.valuation.price_vs_fair_value` removed.
3. Remaining valuation weights pro-rata rescaled to sum to 100, so any
   user customization that was in place stays proportionally intact.

The grading service stops registering the metric in
`SUB_GRADE_METRICS["valuation"]`, so leftover keys in settings would
naturally be skipped — but this migration cleans them out for tidiness
and so the Settings UI doesn't show a phantom 0-weight row.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_drop_price_vs_fair_value"
down_revision: Union[str, None] = "0008_seed_dcf_templates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SINGLETON_ID = 1
TARGET_TOTAL = Decimal(100)
METRIC = "price_vs_fair_value"


def _rescale(weights: dict[str, Any]) -> dict[str, str]:
    """Pro-rata rescale the dict so its values sum to 100 (as Decimal strings).

    Preserves relative weighting any user customization put in place. If the
    remaining weights happen to sum to zero (degenerate case — wouldn't pass
    the schema's sum-to-100 validator anyway), fall back to even distribution.
    """
    decimals = {k: Decimal(str(v)) for k, v in weights.items()}
    total = sum(decimals.values(), start=Decimal(0))
    if total == 0:
        share = TARGET_TOTAL / Decimal(len(decimals))
        return {k: str(share) for k in decimals}
    scale = TARGET_TOTAL / total
    return {k: str(v * scale) for k, v in decimals.items()}


def upgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text(
            "SELECT sub_grade_weights, grade_thresholds "
            "FROM settings WHERE id = :id FOR UPDATE"
        ).bindparams(id=SINGLETON_ID)
    ).first()
    if row is None:
        return

    sub_grade_weights, grade_thresholds = row
    sub_grade_weights = dict(sub_grade_weights or {})
    grade_thresholds = dict(grade_thresholds or {})

    valuation = dict(sub_grade_weights.get("valuation") or {})
    if METRIC in valuation:
        valuation.pop(METRIC)
        if valuation:
            valuation = _rescale(valuation)
        sub_grade_weights["valuation"] = valuation

    grade_thresholds.pop(METRIC, None)

    import json

    conn.execute(
        sa.text(
            "UPDATE settings "
            "SET sub_grade_weights = CAST(:sgw AS jsonb), "
            "    grade_thresholds = CAST(:gt AS jsonb) "
            "WHERE id = :id"
        ).bindparams(
            sgw=json.dumps(sub_grade_weights),
            gt=json.dumps(grade_thresholds),
            id=SINGLETON_ID,
        )
    )


def downgrade() -> None:
    """Restore price_vs_fair_value with its original weight (20) and threshold.

    Other valuation weights are scaled back from sum=100 to sum=80 so the
    re-added 20 brings the total back to 100. Threshold mirrors the values
    from 0002_seed_settings.
    """
    conn = op.get_bind()
    row = conn.execute(
        sa.text(
            "SELECT sub_grade_weights, grade_thresholds "
            "FROM settings WHERE id = :id FOR UPDATE"
        ).bindparams(id=SINGLETON_ID)
    ).first()
    if row is None:
        return

    sub_grade_weights, grade_thresholds = row
    sub_grade_weights = dict(sub_grade_weights or {})
    grade_thresholds = dict(grade_thresholds or {})

    valuation = dict(sub_grade_weights.get("valuation") or {})
    if METRIC not in valuation and valuation:
        # Scale existing weights from sum=100 down to sum=80.
        decimals = {k: Decimal(str(v)) for k, v in valuation.items()}
        total = sum(decimals.values(), start=Decimal(0))
        if total > 0:
            scale = Decimal(80) / total
            valuation = {k: str(v * scale) for k, v in decimals.items()}
        valuation[METRIC] = "20"
        sub_grade_weights["valuation"] = valuation

    grade_thresholds.setdefault(
        METRIC,
        {
            "direction": "lower_better",
            "ranges": [[0.70, 100], [0.85, 85], [1.00, 70], [1.15, 55], [1.30, 35], [None, 10]],
        },
    )

    import json

    conn.execute(
        sa.text(
            "UPDATE settings "
            "SET sub_grade_weights = CAST(:sgw AS jsonb), "
            "    grade_thresholds = CAST(:gt AS jsonb) "
            "WHERE id = :id"
        ).bindparams(
            sgw=json.dumps(sub_grade_weights),
            gt=json.dumps(grade_thresholds),
            id=SINGLETON_ID,
        )
    )
