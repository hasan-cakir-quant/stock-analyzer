"""add job_runs, stock_fair_values, stock_grades

Revision ID: 0016_add_jobs_and_results
Revises: 0015_snapshot_ma_valuations
Create Date: 2026-06-25

Tables backing the background jobs:
  * job_runs          — one row per job execution (status + progress counters).
  * stock_fair_values — latest MA fair value per scenario, per stock (job 1).
  * stock_grades      — latest computed grades per stock (job 4).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_add_jobs_and_results"
down_revision: Union[str, None] = "0015_snapshot_ma_valuations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),  # running | success | failed
        sa.Column("total", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("processed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("succeeded", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_job_runs_type_created", "job_runs", ["job_type", sa.text("created_at DESC")]
    )

    op.create_table(
        "stock_fair_values",
        sa.Column(
            "stock_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stocks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        # { scenario_key: {fair_value: float|null, upside_pct: float|null}, ... }
        sa.Column("scenarios", postgresql.JSONB(), nullable=False),
        sa.Column("current_price", sa.Numeric(), nullable=True),
        sa.Column(
            "computed_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "stock_grades",
        sa.Column(
            "stock_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stocks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("general", sa.Numeric(), nullable=True),
        # Full grades payload (general + sub_grades + breakdown), same shape as
        # the snapshot `grades` blob.
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "computed_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("stock_grades")
    op.drop_table("stock_fair_values")
    op.drop_index("ix_job_runs_type_created", table_name="job_runs")
    op.drop_table("job_runs")
