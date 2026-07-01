"""add financial_imports

Revision ID: 0004_add_financial_imports
Revises: 0003_add_stocks_units_note
Create Date: 2026-05-06

Stores the raw payload of every import (every label the source ships,
including ones we don't yet have schema columns for). One row per
(stock, source, statement, period). Re-importing the same statement
overwrites the row.

Lets us preserve source data we don't currently grade on (R&D, SG&A,
Goodwill, Stock-Based Comp, etc.) so future features can read it back
without re-uploading.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_add_financial_imports"
down_revision: Union[str, None] = "0003_add_stocks_units_note"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "financial_imports",
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
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("parser_id", sa.Text(), nullable=False),
        sa.Column("period", sa.Text(), nullable=False),
        sa.Column("period_end_date", sa.Date(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False),
        sa.Column("source_caption", sa.Text(), nullable=True),
        sa.Column(
            "imported_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "stock_id",
            "source",
            "statement",
            "period",
            name="uq_financial_imports_scope",
        ),
    )
    op.create_index(
        "ix_financial_imports_stock_id", "financial_imports", ["stock_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_financial_imports_stock_id", table_name="financial_imports")
    op.drop_table("financial_imports")
