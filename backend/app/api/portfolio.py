"""Portfolio overview — single call that powers the Home page.

Returns aggregate stats (total stocks, avg general grade, under/over-valued
counts) plus a per-stock summary row. Fair values come from the latest
fair-values job (all scenarios) and grades from the latest grades job, each
falling back to the stock's latest snapshot when a job hasn't run. A small
sparkline series (from snapshots) drives the Home page's grade-trend column.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Snapshot,
    Stock,
    StockFairValue,
    StockGrade,
    StockParameter,
)
from app.db.session import get_db
from app.schemas.portfolio import (
    PortfolioOverview,
    PortfolioStats,
    PortfolioStockRow,
    SparklinePoint,
)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

# How many recent snapshots to include in the per-stock grade sparkline.
SPARKLINE_POINTS = 10

# Scenario whose fair value drives the legacy average_fair_value / upside fields
# and the under/over-valued stats.
HEADLINE_SCENARIO = "normal"


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _latest_snapshot_per_stock(db: Session) -> dict[Any, Snapshot]:
    """Return a `{stock_id: latest_live_snapshot}` map (one query)."""
    rn = (
        func.row_number()
        .over(
            partition_by=Snapshot.stock_id,
            order_by=(Snapshot.created_at.desc(), Snapshot.id.desc()),
        )
        .label("rn")
    )
    subq = (
        select(Snapshot.id.label("id"), rn).where(Snapshot.soft_deleted_at.is_(None)).subquery()
    )
    latest_ids = select(subq.c.id).where(subq.c.rn == 1)
    latest_rows = db.scalars(select(Snapshot).where(Snapshot.id.in_(latest_ids)))
    return {s.stock_id: s for s in latest_rows}


def _sparklines(db: Session) -> dict[Any, list[Snapshot]]:
    """Return `{stock_id: [snapshots, newest first, capped at SPARKLINE_POINTS]}`."""
    rows = db.scalars(
        select(Snapshot)
        .where(Snapshot.soft_deleted_at.is_(None))
        .order_by(Snapshot.stock_id, Snapshot.created_at.desc())
    )
    bucket: dict[Any, list[Snapshot]] = defaultdict(list)
    for s in rows:
        if len(bucket[s.stock_id]) < SPARKLINE_POINTS:
            bucket[s.stock_id].append(s)
    return bucket


def _build_row(
    stock: Stock,
    snap: Snapshot | None,
    sparkline: list[Snapshot],
    fair_value: StockFairValue | None,
    grade: StockGrade | None,
    param: StockParameter | None,
) -> PortfolioStockRow:
    snap_grades = (snap.grades if snap else None) or {}
    snap_summary = ((snap.valuations if snap else None) or {}).get("summary", {}) or {}

    # Grades — prefer the latest grades job, fall back to the snapshot.
    if grade is not None:
        general_grade = grade.general
        sub_grades = {
            name: _to_decimal((sg or {}).get("score"))
            for name, sg in (grade.payload.get("sub_grades") or {}).items()
        }
    else:
        general_grade = _to_decimal(snap_grades.get("general"))
        sub_grades = {
            name: _to_decimal((sg or {}).get("score"))
            for name, sg in (snap_grades.get("sub_grades") or {}).items()
        }

    # Fair values — all scenarios from the fair-values job; the headline
    # (Normal) scenario also fills the legacy average/upside fields.
    scenarios = fair_value.scenarios if fair_value else None
    if scenarios:
        headline = scenarios.get(HEADLINE_SCENARIO) or {}
        average_fair_value = _to_decimal(headline.get("fair_value"))
        upside_pct = _to_decimal(headline.get("upside_pct"))
    else:
        average_fair_value = _to_decimal(snap_summary.get("average"))
        upside_pct = _to_decimal(snap_summary.get("upside_pct"))

    # Current price — live value from parameters, else the snapshot's frozen one.
    current_price = (param.current_price if param else None)
    if current_price is None and snap is not None:
        current_price = snap.current_price_used

    points = [
        SparklinePoint(
            created_at=s.created_at,
            general_grade=_to_decimal((s.grades or {}).get("general")),
        )
        for s in reversed(sparkline)
    ]

    return PortfolioStockRow(
        symbol=stock.symbol,
        currency=stock.currency,
        category=stock.category,
        notes=stock.notes,
        last_updated=snap.created_at if snap else None,
        general_grade=general_grade,
        sub_grades=sub_grades,
        average_fair_value=average_fair_value,
        current_price=current_price,
        upside_pct=upside_pct,
        fair_values=scenarios,
        sparkline=points,
    )


def _aggregate_stats(rows: list[PortfolioStockRow]) -> PortfolioStats:
    total = len(rows)
    grades = [r.general_grade for r in rows if r.general_grade is not None]
    avg = sum(grades, start=Decimal(0)) / Decimal(len(grades)) if grades else None

    undervalued = 0
    overvalued = 0
    for r in rows:
        if r.current_price is None or r.average_fair_value is None:
            continue
        if r.current_price < r.average_fair_value:
            undervalued += 1
        elif r.current_price > r.average_fair_value:
            overvalued += 1

    return PortfolioStats(
        total_stocks=total,
        average_general_grade=avg,
        undervalued_count=undervalued,
        overvalued_count=overvalued,
    )


@router.get("/overview", response_model=PortfolioOverview)
def get_overview(db: Session = Depends(get_db)) -> PortfolioOverview:
    stocks = list(db.scalars(select(Stock).order_by(Stock.symbol)))
    latest = _latest_snapshot_per_stock(db)
    spark = _sparklines(db)
    fair_values = {fv.stock_id: fv for fv in db.scalars(select(StockFairValue))}
    grades = {g.stock_id: g for g in db.scalars(select(StockGrade))}
    params = {p.stock_id: p for p in db.scalars(select(StockParameter))}

    rows = [
        _build_row(
            stock,
            latest.get(stock.id),
            spark.get(stock.id, []),
            fair_values.get(stock.id),
            grades.get(stock.id),
            params.get(stock.id),
        )
        for stock in stocks
    ]
    return PortfolioOverview(stats=_aggregate_stats(rows), stocks=rows)
