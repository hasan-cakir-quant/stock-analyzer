"""add DCF capital-structure parameters

Revision ID: 0007_add_dcf_capital_params
Revises: 0006_add_parameter_templates
Create Date: 2026-05-21

Adds three Parameter Panel fields used by the DCF model when blending
WACC and choosing a discounting convention:

* ``pretax_cost_of_debt`` — yield on the company's debt before tax shield.
* ``tax_rate`` — effective income tax rate for the after-tax cost of debt.
* ``mid_year_convention`` — when true (the realistic default applied in
  the service when null), discount cash flows at (1+r)^(t−0.5) instead of
  year-end. Stored as a nullable bool so "unset" still inherits the
  service-side default.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_add_dcf_capital_params"
down_revision: Union[str, None] = "0006_add_parameter_templates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "stock_parameters",
        sa.Column("pretax_cost_of_debt", sa.Numeric(), nullable=True),
    )
    op.add_column(
        "stock_parameters",
        sa.Column("tax_rate", sa.Numeric(), nullable=True),
    )
    op.add_column(
        "stock_parameters",
        sa.Column("mid_year_convention", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("stock_parameters", "mid_year_convention")
    op.drop_column("stock_parameters", "tax_rate")
    op.drop_column("stock_parameters", "pretax_cost_of_debt")
