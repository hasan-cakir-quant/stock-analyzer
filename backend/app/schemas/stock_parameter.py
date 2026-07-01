"""Pydantic schemas for the `stock_parameters` table — Parameter Panel state."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class StockParameterBase(BaseModel):
    """Persisted per-stock market data — only `current_price` and `beta`."""

    current_price: Decimal | None = None
    beta: Decimal | None = None


class StockParameterUpsert(StockParameterBase):
    """Body for `PUT /stocks/{symbol}/parameters` — full last-used set."""


class ValuationParameters(StockParameterBase):
    """Run-time inputs for `/analyze` and snapshot creation.

    Extends the persisted market-data fields with the two transient target
    multiples. These targets are never written to `stock_parameters`; their
    defaults come from `settings.global_market_assumptions`.
    """

    target_pe: Decimal | None = None
    target_pb: Decimal | None = None
    target_ev_ebitda: Decimal | None = None
    target_ev_ebit: Decimal | None = None
    target_ev_fcf: Decimal | None = None


class StockParameterRead(StockParameterBase):
    """Effective Parameter Panel state — per-stock values merged with global defaults.

    `updated_at` is null when the user has never explicitly saved parameters
    for this stock; in that case every value is sourced from
    `settings.global_market_assumptions`.
    """

    model_config = ConfigDict(from_attributes=True)

    stock_id: UUID
    updated_at: datetime | None = None
