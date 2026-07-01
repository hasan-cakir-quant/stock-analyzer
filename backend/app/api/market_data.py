"""Market-data router — live price, beta, and historical EoQ closes via the
yfinance data provider.

Powers two buttons:

* "Fetch price & beta" on the Parameter Panel — `GET /market-data` returns
  the current_price + beta snapshot.
* "Fetch closing prices" on the Data Entry → Market Data tab —
  `GET /market-data/closing-prices` returns the end-of-quarter close for
  every quarter the stock has a row for (or the periods listed via the
  `periods` query param).

Both endpoints are read-only and ephemeral: they hand the values back to the
frontend, which writes them to the database through the existing auto-save
paths. The yfinance source is unofficial; missing fields come back as null
rather than an error so the UI can still patch in whichever value did resolve.
"""

from __future__ import annotations

import logging
import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api._helpers import get_stock_or_404
from app.db.models import QuarterlyFinancial
from app.db.session import get_db
from app.services.providers import ProviderError, yfinance_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stocks/{symbol}/market-data", tags=["market-data"])

_PERIOD_RE = re.compile(r"^(\d{4})-Q([1-4])$")


class MarketData(BaseModel):
    symbol: str
    # Decimals serialised as strings — matches how the Parameter Panel
    # transports current_price / beta everywhere else.
    current_price: str | None
    beta: str | None
    source: str = "yfinance"


class ClosingPrice(BaseModel):
    period: str
    end_date: date
    closing_price: str | None
    # Populated when the period was resolved but no trading day on/before
    # `end_date` was found in the price history (e.g. pre-IPO quarters).
    reason: str | None = None


class ClosingPrices(BaseModel):
    symbol: str
    source: str = "yfinance"
    prices: list[ClosingPrice]


def _calendar_quarter_end(period: str) -> date | None:
    match = _PERIOD_RE.match(period)
    if not match:
        return None
    year = int(match.group(1))
    quarter = int(match.group(2))
    month_day = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}[quarter]
    return date(year, month_day[0], month_day[1])


@router.get("", response_model=MarketData)
def get_market_data(symbol: str, db: Session = Depends(get_db)) -> MarketData:
    stock = get_stock_or_404(db, symbol)

    try:
        snapshot = yfinance_provider.get_market_snapshot(
            stock.symbol, currency=stock.currency
        )
    except ProviderError as err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(err),
        ) from err

    if snapshot.current_price is None and snapshot.beta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No market data found for '{stock.symbol}'.",
        )

    return MarketData(
        symbol=stock.symbol,
        current_price=snapshot.current_price,
        beta=snapshot.beta,
    )


@router.get("/closing-prices", response_model=ClosingPrices)
def get_closing_prices(
    symbol: str,
    periods: list[str] | None = Query(
        default=None,
        description=(
            "Periods to look up (e.g. 2024-Q1). Omit to use every quarter "
            "this stock already has a row for."
        ),
    ),
    db: Session = Depends(get_db),
) -> ClosingPrices:
    """Resolve each requested quarter's end-of-quarter closing price. The "EoQ"
    close is the last trading day on or before the quarter's end date — using
    the per-row `period_end_date` when stored, otherwise the calendar
    quarter-end (Mar 31 / Jun 30 / Sep 30 / Dec 31)."""
    stock = get_stock_or_404(db, symbol)

    rows = list(
        db.scalars(
            select(QuarterlyFinancial).where(QuarterlyFinancial.stock_id == stock.id)
        )
    )
    end_date_by_period: dict[str, date] = {
        r.period: r.period_end_date for r in rows if r.period_end_date is not None
    }

    # Build the target list. If the caller didn't pass `periods`, use every
    # period that already has a row in the database.
    requested = periods if periods else [r.period for r in rows]
    if not requested:
        return ClosingPrices(symbol=stock.symbol, prices=[])

    # Resolve each period → end date. Reject malformed periods early so the
    # frontend gets a clear 422 instead of a partial response.
    resolved: list[tuple[str, date]] = []
    for period in requested:
        if not _PERIOD_RE.match(period):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid period '{period}'. Expected format YYYY-QN.",
            )
        end = end_date_by_period.get(period) or _calendar_quarter_end(period)
        if end is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Couldn't resolve end date for period '{period}'.",
            )
        resolved.append((period, end))

    try:
        results = yfinance_provider.get_closing_prices(
            stock.symbol, resolved, currency=stock.currency
        )
    except ProviderError as err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(err),
        ) from err

    return ClosingPrices(
        symbol=stock.symbol,
        prices=[
            ClosingPrice(
                period=r.period,
                end_date=r.end_date,
                closing_price=r.closing_price,
                reason=r.reason,
            )
            for r in results
        ],
    )
