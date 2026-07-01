"""Pydantic schemas for the `quarterly_financials` table."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class QuarterlyFinancialBase(BaseModel):
    """All financial line items — every value optional to support partial entry."""

    period_end_date: date | None = None

    # Income statement
    revenue: Decimal | None = None
    cogs: Decimal | None = None
    gross_profit: Decimal | None = None
    operating_expenses: Decimal | None = None
    operating_income: Decimal | None = None
    interest_expense: Decimal | None = None
    pretax_income: Decimal | None = None
    net_income: Decimal | None = None
    eps_basic: Decimal | None = None
    eps_diluted: Decimal | None = None
    ebitda: Decimal | None = None
    shares_outstanding_diluted: Decimal | None = None

    # Balance sheet
    cash_and_equivalents: Decimal | None = None
    short_term_investments: Decimal | None = None
    total_current_assets: Decimal | None = None
    total_assets: Decimal | None = None
    short_term_debt: Decimal | None = None
    total_current_liabilities: Decimal | None = None
    long_term_debt: Decimal | None = None
    total_liabilities: Decimal | None = None
    total_equity: Decimal | None = None
    inventory: Decimal | None = None
    receivables: Decimal | None = None

    # Cash flow
    operating_cash_flow: Decimal | None = None
    capex: Decimal | None = None
    free_cash_flow: Decimal | None = None
    dividends_paid: Decimal | None = None
    stock_buybacks: Decimal | None = None

    # Market data
    closing_price: Decimal | None = None


class QuarterlyFinancialUpsert(QuarterlyFinancialBase):
    """Body for `PUT /stocks/{symbol}/financials/{period}` — period comes from the URL."""


class QuarterlyFinancialRead(QuarterlyFinancialBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    stock_id: UUID
    period: str = Field(description="e.g. 2024-Q3")
    updated_at: datetime
