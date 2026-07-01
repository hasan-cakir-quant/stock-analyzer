"""seed DCF parameter templates

Revision ID: 0008_seed_dcf_templates
Revises: 0007_add_dcf_capital_params
Create Date: 2026-05-21

One-off seed of 48 sector × personality × regime parameter templates
(US, as-of 2026-05-21). Eight sectors, three personalities each
(Conservative / Balanced / Aggressive), two macro regimes (Official:
reported macro numbers; Adjusted: inflation-skeptic overlay with Rf
+2.2pt, MRP +0.5pt, WACC +2pt, CoD +2pt, TG +0.5–1pt per sector).

Insert is idempotent — `ON CONFLICT (name) DO NOTHING` — so re-running
this migration after partial application or after a user has manually
renamed a template won't blow anything away.
"""
from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_seed_dcf_templates"
down_revision: Union[str, None] = "0007_add_dcf_capital_params"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Common across every template.
_TAX_RATE = 0.23
_MID_YEAR_CONVENTION = True

# Sector spec by (sector_name) → fields the personality doesn't override.
# `dr_cons` is the discount_rate (cost of equity) used for the Conservative
# personality; `dr_other` is the rate for Balanced / Aggressive (Conservative
# gets a +50–100bp bump per the source spec). `dg` of None means pre-dividend
# (SaaS Growth) and is omitted from the stored values to match the API's
# `exclude_none=True` write path.
SECTORS_OFFICIAL: dict[str, dict] = {
    "Mega Tech":   {"dr_cons": 0.10,  "dr_other": 0.09,  "tg": 0.03,  "fh": 10, "dg": 0.08, "pe": 25, "evebitda": 18, "cod": 0.048},
    "SaaS Growth": {"dr_cons": 0.12,  "dr_other": 0.11,  "tg": 0.03,  "fh": 10, "dg": None, "pe": 35, "evebitda": 22, "cod": 0.060},
    "Industrial":  {"dr_cons": 0.095, "dr_other": 0.085, "tg": 0.025, "fh": 5,  "dg": 0.05, "pe": 18, "evebitda": 12, "cod": 0.050},
    "Staples":     {"dr_cons": 0.085, "dr_other": 0.075, "tg": 0.025, "fh": 7,  "dg": 0.06, "pe": 22, "evebitda": 15, "cod": 0.045},
    "Utility":     {"dr_cons": 0.075, "dr_other": 0.065, "tg": 0.025, "fh": 5,  "dg": 0.05, "pe": 18, "evebitda": 12, "cod": 0.050},
    "Pharma":      {"dr_cons": 0.090, "dr_other": 0.080, "tg": 0.025, "fh": 7,  "dg": 0.06, "pe": 18, "evebitda": 14, "cod": 0.050},
    "Energy":      {"dr_cons": 0.100, "dr_other": 0.090, "tg": 0.015, "fh": 5,  "dg": 0.04, "pe": 12, "evebitda": 6,  "cod": 0.055},
    "Mid-cap Q":   {"dr_cons": 0.105, "dr_other": 0.095, "tg": 0.025, "fh": 7,  "dg": 0.05, "pe": 18, "evebitda": 12, "cod": 0.055},
}

SECTORS_ADJUSTED: dict[str, dict] = {
    "Mega Tech":   {"dr_cons": 0.120, "dr_other": 0.110, "tg": 0.035, "fh": 10, "dg": 0.08, "pe": 25, "evebitda": 18, "cod": 0.068},
    "SaaS Growth": {"dr_cons": 0.140, "dr_other": 0.130, "tg": 0.035, "fh": 10, "dg": None, "pe": 35, "evebitda": 22, "cod": 0.080},
    "Industrial":  {"dr_cons": 0.115, "dr_other": 0.105, "tg": 0.030, "fh": 5,  "dg": 0.05, "pe": 18, "evebitda": 12, "cod": 0.070},
    "Staples":     {"dr_cons": 0.105, "dr_other": 0.095, "tg": 0.035, "fh": 7,  "dg": 0.06, "pe": 22, "evebitda": 15, "cod": 0.065},
    "Utility":     {"dr_cons": 0.095, "dr_other": 0.085, "tg": 0.030, "fh": 5,  "dg": 0.05, "pe": 18, "evebitda": 12, "cod": 0.070},
    "Pharma":      {"dr_cons": 0.110, "dr_other": 0.100, "tg": 0.030, "fh": 7,  "dg": 0.06, "pe": 18, "evebitda": 14, "cod": 0.070},
    "Energy":      {"dr_cons": 0.120, "dr_other": 0.110, "tg": 0.025, "fh": 5,  "dg": 0.04, "pe": 12, "evebitda": 6,  "cod": 0.075},
    "Mid-cap Q":   {"dr_cons": 0.125, "dr_other": 0.115, "tg": 0.030, "fh": 7,  "dg": 0.05, "pe": 18, "evebitda": 12, "cod": 0.075},
}

PERSONALITIES_OFFICIAL: dict[str, dict] = {
    "Conservative": {"rrr": 0.10, "mos": 0.35},
    "Balanced":     {"rrr": 0.12, "mos": 0.20},
    "Aggressive":   {"rrr": 0.15, "mos": 0.10},
}

PERSONALITIES_ADJUSTED: dict[str, dict] = {
    "Conservative": {"rrr": 0.12, "mos": 0.35},
    "Balanced":     {"rrr": 0.14, "mos": 0.20},
    "Aggressive":   {"rrr": 0.17, "mos": 0.10},
}

REGIMES = [
    # (regime_label, sector_table, personality_table, risk_free, market_risk_premium)
    ("Official", SECTORS_OFFICIAL, PERSONALITIES_OFFICIAL, 0.043, 0.050),
    ("Adjusted", SECTORS_ADJUSTED, PERSONALITIES_ADJUSTED, 0.065, 0.055),
]


def _build_templates() -> list[dict]:
    out: list[dict] = []
    for regime, sectors, personalities, rf, mrp in REGIMES:
        for sector_name, spec in sectors.items():
            for personality, pers in personalities.items():
                dr = spec["dr_cons"] if personality == "Conservative" else spec["dr_other"]
                values: dict = {
                    "risk_free_rate": rf,
                    "market_risk_premium": mrp,
                    "discount_rate": dr,
                    "terminal_growth_rate": spec["tg"],
                    "required_rate_of_return": pers["rrr"],
                    "margin_of_safety": pers["mos"],
                    "forecast_horizon_years": spec["fh"],
                    "target_pe": spec["pe"],
                    "target_ev_ebitda": spec["evebitda"],
                    "pretax_cost_of_debt": spec["cod"],
                    "tax_rate": _TAX_RATE,
                    "mid_year_convention": _MID_YEAR_CONVENTION,
                }
                if spec["dg"] is not None:
                    values["dividend_growth_rate"] = spec["dg"]
                out.append(
                    {
                        "name": f"{sector_name} — {personality} — {regime}",
                        "values": values,
                    }
                )
    return out


def upgrade() -> None:
    insert_sql = sa.text(
        """
        INSERT INTO parameter_templates (name, values)
        VALUES (:name, CAST(:values AS jsonb))
        ON CONFLICT (name) DO NOTHING
        """
    )
    for tmpl in _build_templates():
        op.execute(
            insert_sql.bindparams(
                name=tmpl["name"],
                values=json.dumps(tmpl["values"]),
            )
        )


def downgrade() -> None:
    names = [t["name"] for t in _build_templates()]
    op.execute(
        sa.text(
            "DELETE FROM parameter_templates WHERE name = ANY(:names)"
        ).bindparams(names=names)
    )
