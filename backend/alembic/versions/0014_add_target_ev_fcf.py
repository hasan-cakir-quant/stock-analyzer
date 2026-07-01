"""add target_ev_fcf to global_market_assumptions

Revision ID: 0014_add_target_ev_fcf
Revises: 0013_is_financial_target_pb
Create Date: 2026-06-18

Seeds the EV/FCF valuation model's target multiple (default 18) into the
settings singleton's global_market_assumptions.
"""
from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014_add_target_ev_fcf"
down_revision: Union[str, None] = "0013_is_financial_target_pb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SINGLETON_ID = 1
DEFAULT_TARGET_EV_FCF = 18


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
    gma.setdefault("target_ev_fcf", DEFAULT_TARGET_EV_FCF)
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
    gma.pop("target_ev_fcf", None)
    conn.execute(
        sa.text(
            "UPDATE settings "
            "SET global_market_assumptions = CAST(:gma AS jsonb) "
            "WHERE id = :id"
        ).bindparams(gma=json.dumps(gma), id=SINGLETON_ID)
    )
