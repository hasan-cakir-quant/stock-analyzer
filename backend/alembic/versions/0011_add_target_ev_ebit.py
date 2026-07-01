"""add target_ev_ebit to global_market_assumptions

Revision ID: 0011_add_target_ev_ebit
Revises: 0010_simplify_valuations
Create Date: 2026-06-17

Adds the EV/EBIT valuation model's target multiple to the settings singleton's
`global_market_assumptions`, seeding a default of 14 if not already present.
"""
from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_add_target_ev_ebit"
down_revision: Union[str, None] = "0010_simplify_valuations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SINGLETON_ID = 1
DEFAULT_TARGET_EV_EBIT = 14


def upgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text(
            "SELECT global_market_assumptions FROM settings WHERE id = :id FOR UPDATE"
        ).bindparams(id=SINGLETON_ID)
    ).first()
    if row is None:
        return
    gma = dict(row[0] or {})
    gma.setdefault("target_ev_ebit", DEFAULT_TARGET_EV_EBIT)
    conn.execute(
        sa.text(
            "UPDATE settings "
            "SET global_market_assumptions = CAST(:gma AS jsonb) "
            "WHERE id = :id"
        ).bindparams(gma=json.dumps(gma), id=SINGLETON_ID)
    )


def downgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text(
            "SELECT global_market_assumptions FROM settings WHERE id = :id FOR UPDATE"
        ).bindparams(id=SINGLETON_ID)
    ).first()
    if row is None:
        return
    gma = dict(row[0] or {})
    gma.pop("target_ev_ebit", None)
    conn.execute(
        sa.text(
            "UPDATE settings "
            "SET global_market_assumptions = CAST(:gma AS jsonb) "
            "WHERE id = :id"
        ).bindparams(gma=json.dumps(gma), id=SINGLETON_ID)
    )
