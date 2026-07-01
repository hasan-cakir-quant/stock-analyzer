"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-05

Tables: stocks, quarterly_financials, stock_parameters, snapshots, settings.
Mirrors REQUIREMENTS §5.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stocks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("symbol", sa.Text(), nullable=False, unique=True),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("shares_outstanding", sa.Numeric()),
        sa.Column("notes", sa.Text()),
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

    op.create_table(
        "quarterly_financials",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "stock_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stocks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period", sa.Text(), nullable=False),
        sa.Column("period_end_date", sa.Date()),
        # Income statement
        sa.Column("revenue", sa.Numeric()),
        sa.Column("cogs", sa.Numeric()),
        sa.Column("gross_profit", sa.Numeric()),
        sa.Column("operating_expenses", sa.Numeric()),
        sa.Column("operating_income", sa.Numeric()),
        sa.Column("interest_expense", sa.Numeric()),
        sa.Column("pretax_income", sa.Numeric()),
        sa.Column("net_income", sa.Numeric()),
        sa.Column("eps_basic", sa.Numeric()),
        sa.Column("eps_diluted", sa.Numeric()),
        sa.Column("ebitda", sa.Numeric()),
        sa.Column("shares_outstanding_diluted", sa.Numeric()),
        # Balance sheet
        sa.Column("cash_and_equivalents", sa.Numeric()),
        sa.Column("short_term_investments", sa.Numeric()),
        sa.Column("total_current_assets", sa.Numeric()),
        sa.Column("total_assets", sa.Numeric()),
        sa.Column("short_term_debt", sa.Numeric()),
        sa.Column("total_current_liabilities", sa.Numeric()),
        sa.Column("long_term_debt", sa.Numeric()),
        sa.Column("total_liabilities", sa.Numeric()),
        sa.Column("total_equity", sa.Numeric()),
        sa.Column("inventory", sa.Numeric()),
        sa.Column("receivables", sa.Numeric()),
        # Cash flow
        sa.Column("operating_cash_flow", sa.Numeric()),
        sa.Column("capex", sa.Numeric()),
        sa.Column("free_cash_flow", sa.Numeric()),
        sa.Column("dividends_paid", sa.Numeric()),
        sa.Column("stock_buybacks", sa.Numeric()),
        # Market data
        sa.Column("closing_price", sa.Numeric()),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("stock_id", "period", name="uq_quarterly_financials_stock_period"),
    )
    op.create_index(
        "ix_quarterly_financials_stock_id",
        "quarterly_financials",
        ["stock_id"],
    )

    op.create_table(
        "stock_parameters",
        sa.Column(
            "stock_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stocks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("current_price", sa.Numeric()),
        sa.Column("risk_free_rate", sa.Numeric()),
        sa.Column("market_risk_premium", sa.Numeric()),
        sa.Column("discount_rate", sa.Numeric()),
        sa.Column("terminal_growth_rate", sa.Numeric()),
        sa.Column("required_rate_of_return", sa.Numeric()),
        sa.Column("margin_of_safety", sa.Numeric()),
        sa.Column("forecast_horizon_years", sa.Integer()),
        sa.Column("dividend_growth_rate", sa.Numeric()),
        sa.Column("target_pe", sa.Numeric()),
        sa.Column("target_ev_ebitda", sa.Numeric()),
        sa.Column("beta", sa.Numeric()),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "snapshots",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "stock_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stocks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Denormalised for fast cross-stock browsing without a join.
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("note", sa.Text()),
        sa.Column("financials_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("parameters_used", postgresql.JSONB(), nullable=False),
        sa.Column("settings_used", postgresql.JSONB(), nullable=False),
        sa.Column("valuations", postgresql.JSONB(), nullable=False),
        sa.Column("grades", postgresql.JSONB(), nullable=False),
        sa.Column("growth_metrics", postgresql.JSONB(), nullable=False),
        sa.Column("current_price_used", sa.Numeric()),
        sa.Column("soft_deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_snapshots_stock_id", "snapshots", ["stock_id"])
    op.create_index("ix_snapshots_symbol", "snapshots", ["symbol"])
    op.create_index("ix_snapshots_created_at", "snapshots", ["created_at"])
    # Partial index — the default-listing path only ever queries live rows.
    op.create_index(
        "ix_snapshots_active",
        "snapshots",
        ["created_at"],
        postgresql_where=sa.text("soft_deleted_at IS NULL"),
    )

    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("general_grade_weights", postgresql.JSONB(), nullable=False),
        sa.Column("sub_grade_weights", postgresql.JSONB(), nullable=False),
        sa.Column("grade_thresholds", postgresql.JSONB(), nullable=False),
        sa.Column("currency_format", postgresql.JSONB(), nullable=False),
        sa.Column("global_market_assumptions", postgresql.JSONB(), nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Singleton — the row exists or does not; nothing else is allowed.
        sa.CheckConstraint("id = 1", name="ck_settings_singleton"),
    )


def downgrade() -> None:
    op.drop_table("settings")
    op.drop_index("ix_snapshots_active", table_name="snapshots")
    op.drop_index("ix_snapshots_created_at", table_name="snapshots")
    op.drop_index("ix_snapshots_symbol", table_name="snapshots")
    op.drop_index("ix_snapshots_stock_id", table_name="snapshots")
    op.drop_table("snapshots")
    op.drop_table("stock_parameters")
    op.drop_index("ix_quarterly_financials_stock_id", table_name="quarterly_financials")
    op.drop_table("quarterly_financials")
    op.drop_table("stocks")
