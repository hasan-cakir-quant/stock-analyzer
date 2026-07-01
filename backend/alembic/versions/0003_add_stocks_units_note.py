"""add stocks.units_note

Revision ID: 0003_add_stocks_units_note
Revises: 0002_seed_settings
Create Date: 2026-05-05

Free-text note describing the unit convention for the stock's financials
(e.g. "Quarterly Data | Millions of US $ except per share data"). The
import flow auto-fills it from the source caption on first import; the
user can also edit it manually via the Edit Metadata dialog.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_add_stocks_units_note"
down_revision: Union[str, None] = "0002_seed_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("stocks", sa.Column("units_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("stocks", "units_note")
