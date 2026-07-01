"""Pydantic schemas for the singleton `settings` row."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Strict integer total — UI inputs are whole numbers; Decimal makes the math exact.
WEIGHT_TOTAL = Decimal(100)


class GeneralGradeWeights(BaseModel):
    """Seven sub-grade weights — must sum to 100."""

    profitability: Decimal
    valuation: Decimal
    financial_strength: Decimal
    growth: Decimal
    efficiency: Decimal
    safety: Decimal
    dividend: Decimal

    @model_validator(mode="after")
    def _sum_to_100(self) -> GeneralGradeWeights:
        total = (
            self.profitability
            + self.valuation
            + self.financial_strength
            + self.growth
            + self.efficiency
            + self.safety
            + self.dividend
        )
        if total != WEIGHT_TOTAL:
            raise ValueError(
                f"General grade weights must sum to 100 (got {total})."
            )
        return self


class CurrencyFormat(BaseModel):
    thousands_separator: str = ","
    decimal_separator: str = "."
    decimal_places: int = Field(default=2, ge=0, le=8)


class GlobalMarketAssumptions(BaseModel):
    """Defaults that pre-fill the run-time valuation inputs.

    Only the two target multiples remain — Target P/E and Target EV/EBITDA —
    which seed the Valuations panel's editable inputs on each stock page.
    """

    target_pe: Decimal | None = None
    target_pb: Decimal | None = None
    target_ev_ebitda: Decimal | None = None
    target_ev_ebit: Decimal | None = None
    target_ev_fcf: Decimal | None = None


# Sub-grade internal weights and grade thresholds are open-ended (per-metric
# nested dicts whose keys evolve as new metrics are added). Keep them as
# untyped JSONB blobs at the schema layer; the grading engine validates shape.


class SettingsBase(BaseModel):
    general_grade_weights: GeneralGradeWeights
    sub_grade_weights: dict[str, dict[str, Decimal]]
    grade_thresholds: dict[str, dict[str, Any]]
    currency_format: CurrencyFormat
    global_market_assumptions: GlobalMarketAssumptions

    @model_validator(mode="after")
    def _sub_grade_weights_sum_to_100(self) -> SettingsBase:
        for sub_grade, weights in self.sub_grade_weights.items():
            if not weights:
                raise ValueError(f"Sub-grade '{sub_grade}' has no metric weights.")
            total = sum(weights.values(), start=Decimal(0))
            if total != WEIGHT_TOTAL:
                raise ValueError(
                    f"Sub-grade '{sub_grade}' internal weights must sum to 100 "
                    f"(got {total})."
                )
        return self


class SettingsUpdate(SettingsBase):
    """Body for `PUT /settings` — full replace (debounce-friendly)."""


class SettingsRead(SettingsBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    updated_at: datetime
