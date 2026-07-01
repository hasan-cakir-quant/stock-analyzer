"""add parameter_templates

Revision ID: 0006_add_parameter_templates
Revises: 0005_add_stocks_cik
Create Date: 2026-05-21

Reusable named bundles of Parameter Panel assumptions. Each row stores a
JSONB `values` blob keyed by the same field names as `stock_parameters`
(excluding `current_price` and `beta`, which are inherently per-stock).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_add_parameter_templates"
down_revision: Union[str, None] = "0005_add_stocks_cik"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_table("parameter_templates")
