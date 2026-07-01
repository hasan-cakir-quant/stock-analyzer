"""Pydantic schemas for the portfolio overview endpoint (Home page)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class SparklinePoint(BaseModel):
    created_at: datetime
    general_grade: Decimal | None = None


class PortfolioStockRow(BaseModel):
    symbol: str
    currency: str
    category: str | None = None
    notes: str | None = None
    last_updated: datetime | None = None
    general_grade: Decimal | None = None
    sub_grades: dict[str, Decimal | None] = {}
    average_fair_value: Decimal | None = None
    current_price: Decimal | None = None
    upside_pct: Decimal | None = None
    # Per-scenario fair values from the latest fair-values job:
    # { scenario_key: {"fair_value": float|None, "upside_pct": float|None} }.
    fair_values: dict[str, Any] | None = None
    sparkline: list[SparklinePoint] = []


class PortfolioStats(BaseModel):
    total_stocks: int
    average_general_grade: Decimal | None = None
    undervalued_count: int
    overvalued_count: int


class PortfolioOverview(BaseModel):
    stats: PortfolioStats
    stocks: list[PortfolioStockRow]
