"""Pydantic schemas for the `snapshots` table."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.stock_parameter import ValuationParameters


class SnapshotCreate(BaseModel):
    """Body for `POST /stocks/{symbol}/snapshots`.

    The server re-runs Full Analysis using the supplied market data + target
    multiples plus the current quarterly data and settings, then freezes the
    result. `parameters` is optional — omit it to use whatever is already
    saved per-stock + the global defaults.
    """

    parameters: ValuationParameters = Field(default_factory=ValuationParameters)
    note: str | None = None
    # MA-based valuation matrix computed on the frontend and frozen as-is.
    ma_valuations: dict[str, Any] | None = None


class SnapshotListItem(BaseModel):
    """Compact row for snapshot lists (per-stock log + cross-stock browser).

    `general_grade` and `average_fair_value` are denormalised out of the
    JSONB blobs by the router so the listing UI doesn't need to crack
    the full payload open.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    stock_id: UUID
    symbol: str
    created_at: datetime
    note: str | None = None
    current_price_used: Decimal | None = None
    soft_deleted_at: datetime | None = None
    general_grade: Decimal | None = None
    average_fair_value: Decimal | None = None


class SnapshotRead(SnapshotListItem):
    """Full snapshot detail."""

    model_config = ConfigDict(from_attributes=True)

    financials_snapshot: list[dict[str, Any]]
    parameters_used: dict[str, Any]
    settings_used: dict[str, Any]
    valuations: dict[str, Any]
    grades: dict[str, Any]
    growth_metrics: dict[str, Any]
    ma_valuations: dict[str, Any] | None = None
