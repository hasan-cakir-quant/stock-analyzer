"""add stocks.cik

Revision ID: 0005_add_stocks_cik
Revises: 0004_add_financial_imports
Create Date: 2026-05-14

SEC EDGAR Central Index Key for the issuer. Stored as the canonical
zero-padded 10-digit string (e.g. "0000320193" for AAPL) so it round-
trips cleanly with EDGAR URLs. Nullable — populated on demand by the
"Fetch CIK" button on the Stock page, or hand-edited via Edit Metadata.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_add_stocks_cik"
down_revision: Union[str, None] = "0004_add_financial_imports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("stocks", sa.Column("cik", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("stocks", "cik")
