"""Pydantic schemas for the `stocks` table."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StockBase(BaseModel):
    """Fields shared by create/update/read."""

    currency: str = Field(min_length=1, max_length=8)
    shares_outstanding: Decimal | None = None
    notes: str | None = None
    # Free-text grouping label for the portfolio page (e.g. "Tech").
    category: str | None = Field(default=None, max_length=64)
    # Bank / financial institution — EV-based valuations opt out.
    is_financial: bool = False
    # Free-text reminder of the units the financial values are stored in
    # (e.g. "Millions of US $"). Surfaced in the Data Entry header so the
    # user always knows what scale they're typing in.
    units_note: str | None = None
    # SEC EDGAR CIK (zero-padded 10-digit string).
    cik: str | None = Field(default=None, max_length=10)


class StockCreate(StockBase):
    # Symbol is set on creation and read-only thereafter (FR-3.1.4 / FR-3.1.3).
    symbol: str = Field(min_length=1, max_length=32)


class StockUpdate(BaseModel):
    """Partial update — every field optional; symbol is immutable."""

    currency: str | None = Field(default=None, min_length=1, max_length=8)
    shares_outstanding: Decimal | None = None
    notes: str | None = None
    category: str | None = Field(default=None, max_length=64)
    is_financial: bool | None = None
    units_note: str | None = None
    cik: str | None = Field(default=None, max_length=10)


class StockRead(StockBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    symbol: str
    created_at: datetime
    updated_at: datetime
