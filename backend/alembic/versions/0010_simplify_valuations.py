"""simplify valuations: drop templates, trim assumptions & stock_parameters

Revision ID: 0010_simplify_valuations
Revises: 0009_drop_price_vs_fair_value
Create Date: 2026-06-16

The app now runs only two valuation models — P/E Based and EV/EBITDA — and
the parameter-templates feature is gone. This migration aligns the schema:

1. Drop the `parameter_templates` table.
2. Trim `settings.global_market_assumptions` to just `target_pe` and
   `target_ev_ebitda` (preserving existing values; seeding 18 / 12 if absent).
3. Drop the now-unused valuation-assumption columns from `stock_parameters`,
   keeping only the per-stock market data (`current_price`, `beta`). Target
   multiples are transient run-time inputs, not persisted per-stock.
"""
from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_simplify_valuations"
down_revision: Union[str, None] = "0009_drop_price_vs_fair_value"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SINGLETON_ID = 1

# Columns dropped from stock_parameters (everything except current_price, beta).
# (name, sqlalchemy type, default for downgrade re-add)
_DROPPED_COLUMNS = [
    ("risk_free_rate", sa.Numeric()),
    ("market_risk_premium", sa.Numeric()),
    ("discount_rate", sa.Numeric()),
    ("terminal_growth_rate", sa.Numeric()),
    ("required_rate_of_return", sa.Numeric()),
    ("margin_of_safety", sa.Numeric()),
    ("forecast_horizon_years", sa.Integer()),
    ("dividend_growth_rate", sa.Numeric()),
    ("target_pe", sa.Numeric()),
    ("target_ev_ebitda", sa.Numeric()),
    ("pretax_cost_of_debt", sa.Numeric()),
    ("tax_rate", sa.Numeric()),
    ("mid_year_convention", sa.Boolean()),
]

# Full assumption set restored on downgrade (mirrors 0002_seed_settings).
_FULL_ASSUMPTIONS = {
    "risk_free_rate": 0.045,
    "market_risk_premium": 0.055,
    "discount_rate": 0.10,
    "terminal_growth_rate": 0.025,
    "required_rate_of_return": 0.10,
    "margin_of_safety": 0.25,
    "forecast_horizon_years": 5,
    "dividend_growth_rate": 0.05,
    "target_pe": 18,
    "target_ev_ebitda": 12,
}


def upgrade() -> None:
    # 1. Drop the parameter_templates table.
    op.drop_table("parameter_templates")

    # 2. Trim global_market_assumptions to the two surviving targets.
    conn = op.get_bind()
    row = conn.execute(
        sa.text(
            "SELECT global_market_assumptions FROM settings "
            "WHERE id = :id FOR UPDATE"
        ).bindparams(id=SINGLETON_ID)
    ).first()
    if row is not None:
        current = dict(row[0] or {})
        trimmed = {
            "target_pe": current.get("target_pe", 18),
            "target_ev_ebitda": current.get("target_ev_ebitda", 12),
        }
        conn.execute(
            sa.text(
                "UPDATE settings "
                "SET global_market_assumptions = CAST(:gma AS jsonb) "
                "WHERE id = :id"
            ).bindparams(gma=json.dumps(trimmed), id=SINGLETON_ID)
        )

    # 3. Drop the obsolete stock_parameters columns.
    for name, _type in _DROPPED_COLUMNS:
        op.drop_column("stock_parameters", name)


def downgrade() -> None:
    # 3'. Re-add the stock_parameters columns (nullable, no data restored).
    for name, col_type in _DROPPED_COLUMNS:
        op.add_column("stock_parameters", sa.Column(name, col_type, nullable=True))

    # 2'. Restore the full assumption set (values reset to seed defaults).
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE settings "
            "SET global_market_assumptions = CAST(:gma AS jsonb) "
            "WHERE id = :id"
        ).bindparams(gma=json.dumps(_FULL_ASSUMPTIONS), id=SINGLETON_ID)
    )

    # 1'. Recreate the parameter_templates table.
    op.create_table(
        "parameter_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("values", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
