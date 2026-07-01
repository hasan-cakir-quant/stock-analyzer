"""Data-availability overview — per-stock coverage of financials & prices.

`GET /api/data/availability` returns one row per stock summarising how much
data we hold: how many quarters are stored, the latest reported quarter (and its
end date), whether that latest quarter carries an end-of-quarter closing price,
and whether a live current price / beta is on file. Powers the Data Availability
screen, whose per-row "Refresh" button calls `POST /stocks/{symbol}/refresh`.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    QuarterlyFinancial,
    Stock,
    StockFairValue,
    StockGrade,
    StockParameter,
)
from app.db.session import get_db

router = APIRouter(prefix="/data", tags=["data-availability"])


class DataAvailabilityItem(BaseModel):
    symbol: str
    currency: str
    category: str | None
    is_financial: bool
    # Financials coverage
    quarters_count: int
    latest_quarter: str | None
    latest_quarter_end_date: date | None
    # Price coverage
    closing_price_count: int
    latest_quarter_has_close: bool
    has_current_price: bool
    current_price: Decimal | None
    beta: Decimal | None
    # Last-updated timestamps per data type (None if never).
    financials_updated_at: datetime | None
    price_updated_at: datetime | None
    fair_values_at: datetime | None
    grades_at: datetime | None


@router.get("/availability", response_model=list[DataAvailabilityItem])
def data_availability(db: Session = Depends(get_db)) -> list[DataAvailabilityItem]:
    stocks = list(db.scalars(select(Stock).order_by(Stock.symbol)))

    # Per-stock counts: total quarters and how many carry a closing price.
    # func.count(column) counts non-null values, so close_cnt skips NULL closes.
    count_rows = db.execute(
        select(
            QuarterlyFinancial.stock_id,
            func.count().label("cnt"),
            func.count(QuarterlyFinancial.closing_price).label("close_cnt"),
            func.max(QuarterlyFinancial.updated_at).label("fin_updated"),
        ).group_by(QuarterlyFinancial.stock_id)
    ).all()
    counts = {r.stock_id: r for r in count_rows}

    # The latest quarter per stock — join the max(period) back to its full row
    # so we can read its end date and closing price.
    latest_sub = (
        select(
            QuarterlyFinancial.stock_id,
            func.max(QuarterlyFinancial.period).label("mp"),
        )
        .group_by(QuarterlyFinancial.stock_id)
        .subquery()
    )
    latest_rows = {
        row.stock_id: row
        for row in db.scalars(
            select(QuarterlyFinancial).join(
                latest_sub,
                (QuarterlyFinancial.stock_id == latest_sub.c.stock_id)
                & (QuarterlyFinancial.period == latest_sub.c.mp),
            )
        )
    }

    params = {p.stock_id: p for p in db.scalars(select(StockParameter))}
    fair_values = {fv.stock_id: fv for fv in db.scalars(select(StockFairValue))}
    grades = {g.stock_id: g for g in db.scalars(select(StockGrade))}

    items: list[DataAvailabilityItem] = []
    for stock in stocks:
        cnt_row = counts.get(stock.id)
        latest = latest_rows.get(stock.id)
        param = params.get(stock.id)
        fv = fair_values.get(stock.id)
        grade = grades.get(stock.id)
        items.append(
            DataAvailabilityItem(
                symbol=stock.symbol,
                currency=stock.currency,
                category=stock.category,
                is_financial=stock.is_financial,
                quarters_count=int(cnt_row.cnt) if cnt_row else 0,
                latest_quarter=latest.period if latest else None,
                latest_quarter_end_date=latest.period_end_date if latest else None,
                closing_price_count=int(cnt_row.close_cnt) if cnt_row else 0,
                latest_quarter_has_close=bool(
                    latest and latest.closing_price is not None
                ),
                has_current_price=bool(param and param.current_price is not None),
                current_price=param.current_price if param else None,
                beta=param.beta if param else None,
                financials_updated_at=cnt_row.fin_updated if cnt_row else None,
                price_updated_at=param.updated_at if param else None,
                fair_values_at=fv.computed_at if fv else None,
                grades_at=grade.computed_at if grade else None,
            )
        )
    return items
