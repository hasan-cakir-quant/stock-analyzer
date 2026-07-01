"""add stocks.is_financial and target_pb assumption

Revision ID: 0013_is_financial_target_pb
Revises: 0012_add_stocks_category
Create Date: 2026-06-18

1. `stocks.is_financial` — flags banks/financials so EV-based valuations
   (EV/EBITDA, EV/EBIT) opt out; defaults to false.
2. Seeds `target_pb` (default 1.5) into settings.global_market_assumptions
   for the new P/B-based valuation model.
"""
from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_is_financial_target_pb"
down_revision: Union[str, None] = "0012_add_stocks_category"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SINGLETON_ID = 1
DEFAULT_TARGET_PB = 1.5


def upgrade() -> None:
    op.add_column(
        "stocks",
        sa.Column(
            "is_financial",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    conn = op.get_bind()
    row = conn.execute(
        sa.text(
            "SELECT global_market_assumptions FROM settings WHERE id = :id FOR UPDATE"
        ).bindparams(id=SINGLETON_ID)
    ).first()
    if row is not None:
        gma = dict(row[0] or {})
        gma.setdefault("target_pb", DEFAULT_TARGET_PB)
        conn.execute(
            sa.text(
                "UPDATE settings "
                "SET global_market_assumptions = CAST(:gma AS jsonb) "
                "WHERE id = :id"
            ).bindparams(gma=json.dumps(gma), id=SINGLETON_ID)
        )


def downgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text(
            "SELECT global_market_assumptions FROM settings WHERE id = :id FOR UPDATE"
        ).bindparams(id=SINGLETON_ID)
    ).first()
    if row is not None:
        gma = dict(row[0] or {})
        gma.pop("target_pb", None)
        conn.execute(
            sa.text(
                "UPDATE settings "
                "SET global_market_assumptions = CAST(:gma AS jsonb) "
                "WHERE id = :id"
            ).bindparams(gma=json.dumps(gma), id=SINGLETON_ID)
        )

    op.drop_column("stocks", "is_financial")
