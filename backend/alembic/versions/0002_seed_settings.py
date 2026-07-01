"""seed singleton settings row

Revision ID: 0002_seed_settings
Revises: 0001_initial_schema
Create Date: 2026-05-05

Inserts the lone `settings` row (id=1) with sensible defaults for grade
weights, sub-grade internal weights, per-metric threshold tables, currency
formatting, and global market assumptions.

Threshold table format:
  metric -> {"direction": "higher_better" | "lower_better",
             "ranges": [[boundary, score], ...]}
Walked top-to-bottom; first match wins. `boundary` is a lower bound for
higher_better metrics, an upper bound for lower_better metrics, or null
for the catch-all final entry.
"""
from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_seed_settings"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


GENERAL_GRADE_WEIGHTS = {
    "profitability": 20,
    "valuation": 20,
    "financial_strength": 15,
    "growth": 15,
    "efficiency": 10,
    "safety": 10,
    "dividend": 10,
}

SUB_GRADE_WEIGHTS = {
    "profitability": {
        "roe": 20,
        "roa": 15,
        "roic": 20,
        "net_margin": 15,
        "gross_margin": 15,
        "operating_margin": 15,
    },
    "financial_strength": {
        "debt_to_equity": 25,
        "current_ratio": 15,
        "quick_ratio": 15,
        "interest_coverage": 25,
        "debt_to_ebitda": 20,
    },
    "valuation": {
        "pe": 20,
        "pb": 15,
        "ps": 10,
        "ev_ebitda": 20,
        "peg": 15,
        "price_vs_fair_value": 20,
    },
    "growth": {
        "revenue_growth": 30,
        "eps_growth": 30,
        "fcf_growth": 25,
        "book_value_growth": 15,
    },
    "efficiency": {
        "asset_turnover": 35,
        "inventory_turnover": 30,
        "cash_conversion_cycle": 35,
    },
    "safety": {
        "beta": 20,
        "altman_z_score": 30,
        "piotroski_f_score": 30,
        "debt_levels": 20,
    },
    "dividend": {
        "dividend_yield": 30,
        "payout_ratio": 20,
        "dividend_growth_rate": 25,
        "consecutive_growth_years": 25,
    },
}


def _hb(*ranges):
    return {"direction": "higher_better", "ranges": [list(r) for r in ranges]}


def _lb(*ranges):
    return {"direction": "lower_better", "ranges": [list(r) for r in ranges]}


GRADE_THRESHOLDS = {
    # Profitability — ratios expressed as decimals (e.g. 0.25 = 25% ROE)
    "roe": _hb((0.25, 100), (0.20, 85), (0.15, 70), (0.10, 55), (0.05, 35), (None, 10)),
    "roa": _hb((0.15, 100), (0.10, 85), (0.07, 70), (0.04, 55), (0.02, 35), (None, 10)),
    "roic": _hb((0.20, 100), (0.15, 85), (0.10, 70), (0.07, 55), (0.04, 35), (None, 10)),
    "net_margin": _hb((0.20, 100), (0.15, 85), (0.10, 70), (0.05, 55), (0.02, 35), (None, 10)),
    "gross_margin": _hb((0.50, 100), (0.40, 85), (0.30, 70), (0.20, 55), (0.10, 35), (None, 10)),
    "operating_margin": _hb(
        (0.25, 100), (0.18, 85), (0.12, 70), (0.07, 55), (0.03, 35), (None, 10)
    ),
    # Financial Strength
    "debt_to_equity": _lb((0.30, 100), (0.50, 85), (1.0, 70), (1.5, 55), (2.0, 35), (None, 10)),
    "current_ratio": _hb((2.0, 100), (1.5, 85), (1.2, 70), (1.0, 55), (0.8, 35), (None, 10)),
    "quick_ratio": _hb((1.5, 100), (1.0, 85), (0.8, 70), (0.6, 55), (0.4, 35), (None, 10)),
    "interest_coverage": _hb((15, 100), (10, 85), (5, 70), (3, 55), (1.5, 35), (None, 10)),
    "debt_to_ebitda": _lb((1, 100), (2, 85), (3, 70), (4, 55), (5, 35), (None, 10)),
    # Valuation — multiples; lower is cheaper (better)
    "pe": _lb((10, 100), (15, 85), (20, 70), (25, 55), (35, 35), (None, 10)),
    "pb": _lb((1, 100), (2, 85), (3, 70), (4, 55), (6, 35), (None, 10)),
    "ps": _lb((1, 100), (2, 85), (3, 70), (5, 55), (8, 35), (None, 10)),
    "ev_ebitda": _lb((8, 100), (12, 85), (16, 70), (20, 55), (25, 35), (None, 10)),
    "peg": _lb((1.0, 100), (1.5, 85), (2.0, 70), (2.5, 55), (3.0, 35), (None, 10)),
    # price as fraction of average fair value (0.7 = trading at 70% of FV)
    "price_vs_fair_value": _lb(
        (0.70, 100), (0.85, 85), (1.00, 70), (1.15, 55), (1.30, 35), (None, 10)
    ),
    # Growth — CAGRs as decimals
    "revenue_growth": _hb((0.20, 100), (0.12, 85), (0.07, 70), (0.03, 55), (0, 35), (None, 10)),
    "eps_growth": _hb((0.20, 100), (0.12, 85), (0.07, 70), (0.03, 55), (0, 35), (None, 10)),
    "fcf_growth": _hb((0.15, 100), (0.10, 85), (0.05, 70), (0.02, 55), (0, 35), (None, 10)),
    "book_value_growth": _hb(
        (0.15, 100), (0.10, 85), (0.06, 70), (0.03, 55), (0, 35), (None, 10)
    ),
    # Efficiency
    "asset_turnover": _hb((1.0, 100), (0.7, 85), (0.5, 70), (0.3, 55), (0.15, 35), (None, 10)),
    "inventory_turnover": _hb((10, 100), (6, 85), (4, 70), (2.5, 55), (1.5, 35), (None, 10)),
    # cash conversion cycle in days — shorter is better
    "cash_conversion_cycle": _lb(
        (30, 100), (60, 85), (90, 70), (120, 55), (180, 35), (None, 10)
    ),
    # Safety
    "beta": _lb((0.7, 100), (1.0, 85), (1.3, 70), (1.6, 55), (2.0, 35), (None, 10)),
    "altman_z_score": _hb((3.0, 100), (2.6, 85), (1.8, 70), (1.0, 55), (None, 15)),
    "piotroski_f_score": _hb((8, 100), (7, 85), (6, 70), (5, 55), (3, 35), (None, 15)),
    # debt-to-total-assets
    "debt_levels": _lb((0.20, 100), (0.35, 85), (0.50, 70), (0.65, 55), (0.80, 35), (None, 10)),
    # Dividend
    "dividend_yield": _hb(
        (0.05, 100), (0.04, 85), (0.03, 70), (0.02, 55), (0.01, 35), (None, 15)
    ),
    "payout_ratio": _lb(
        (0.40, 100), (0.55, 85), (0.70, 70), (0.85, 55), (1.0, 35), (None, 10)
    ),
    "dividend_growth_rate": _hb(
        (0.10, 100), (0.07, 85), (0.04, 70), (0.02, 55), (0, 35), (None, 15)
    ),
    "consecutive_growth_years": _hb((20, 100), (10, 85), (5, 70), (3, 55), (1, 35), (None, 10)),
}

CURRENCY_FORMAT = {
    "thousands_separator": ",",
    "decimal_separator": ".",
    "decimal_places": 2,
}

GLOBAL_MARKET_ASSUMPTIONS = {
    "risk_free_rate": 0.045,
    "market_risk_premium": 0.055,
    "discount_rate": 0.10,
    "terminal_growth_rate": 0.025,
    "required_rate_of_return": 0.10,
    "margin_of_safety": 0.25,
    "forecast_horizon_years": 5,
    "dividend_growth_rate": 0.05,
    "target_pe": 18,
    "target_ev_ebitda": 12,
}


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO settings (
                id,
                general_grade_weights,
                sub_grade_weights,
                grade_thresholds,
                currency_format,
                global_market_assumptions
            ) VALUES (
                1,
                CAST(:general AS jsonb),
                CAST(:sub AS jsonb),
                CAST(:thresholds AS jsonb),
                CAST(:currency AS jsonb),
                CAST(:assumptions AS jsonb)
            )
            ON CONFLICT (id) DO NOTHING
            """
        ).bindparams(
            general=json.dumps(GENERAL_GRADE_WEIGHTS),
            sub=json.dumps(SUB_GRADE_WEIGHTS),
            thresholds=json.dumps(GRADE_THRESHOLDS),
            currency=json.dumps(CURRENCY_FORMAT),
            assumptions=json.dumps(GLOBAL_MARKET_ASSUMPTIONS),
        )
    )


def downgrade() -> None:
    op.execute("DELETE FROM settings WHERE id = 1")
