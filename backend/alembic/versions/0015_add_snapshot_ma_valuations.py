"""add snapshots.ma_valuations

Revision ID: 0015_snapshot_ma_valuations
Revises: 0014_add_target_ev_fcf
Create Date: 2026-06-22

Stores the MA-based valuation matrix (latest MA4/MA8/MA12 fair values per
method, at the chosen scenario) frozen with each snapshot. Nullable — older
snapshots have none.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_snapshot_ma_valuations"
down_revision: Union[str, None] = "0014_add_target_ev_fcf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "snapshots",
        sa.Column("ma_valuations", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("snapshots", "ma_valuations")
