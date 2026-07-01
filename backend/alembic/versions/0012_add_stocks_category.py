"""add category column to stocks

Revision ID: 0012_add_stocks_category
Revises: 0011_add_target_ev_ebit
Create Date: 2026-06-18

Free-text grouping label for the portfolio page (e.g. "Tech", "Watchlist").
Nullable — existing stocks are uncategorized until the user sets one.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_add_stocks_category"
down_revision: Union[str, None] = "0011_add_target_ev_ebit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("stocks", sa.Column("category", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("stocks", "category")
