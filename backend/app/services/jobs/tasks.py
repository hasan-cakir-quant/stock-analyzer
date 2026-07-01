"""Background-job work — per-stock primitives + the bulk job drivers.

Each data operation is a single-stock function (`*_for_stock`) so it can be run
both individually (per-stock endpoints) and across the whole portfolio (the bulk
jobs, via `_run_per_stock`). Every function commits its own changes and returns
True on success / False on a non-fatal skip; hard failures raise (the bulk
driver catches and counts them, the per-stock endpoint turns them into HTTP
errors).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.cik import lookup_and_save_cik
from app.api.financials import (
    bulk_upsert,
    import_preview_edgar,
)
from app.api.market_data import get_closing_prices, get_market_data
from app.db.models import (
    QuarterlyFinancial,
    Setting,
    Stock,
    StockFairValue,
    StockGrade,
    StockParameter,
)
from app.db.models.setting import SETTINGS_SINGLETON_ID
from app.schemas.financial_import import BulkUpsertRequest, BulkUpsertRow, ImportContext
from app.services.analysis import to_quarter
from app.services.grading import GradingInputs, compute_grades
from app.services.grading import to_payload as grades_payload
from app.services.ma_valuation import all_scenario_fair_values, normal_fair_value
from app.services.valuations._helpers import latest_shares_outstanding

logger = logging.getLogger(__name__)


class Progress(Protocol):
    def __call__(
        self,
        *,
        total: int | None = None,
        processed: int | None = None,
        succeeded: int | None = None,
        failed: int | None = None,
    ) -> None: ...


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _now() -> datetime:
    return datetime.now().astimezone()


def _quarters_for_stock(db: Session, stock_id: Any) -> list[QuarterlyFinancial]:
    return list(
        db.scalars(
            select(QuarterlyFinancial)
            .where(QuarterlyFinancial.stock_id == stock_id)
            .order_by(QuarterlyFinancial.period)
        )
    )


def _stock_ids_with_quarters(db: Session) -> set[Any]:
    return set(db.scalars(select(QuarterlyFinancial.stock_id).distinct()))


# ---------------------------------------------------------------------------
# Per-stock primitives — usable individually or from the bulk jobs.
# ---------------------------------------------------------------------------


def fair_value_for_stock(db: Session, stock: Stock) -> bool:
    """Compute + store all-scenario fair values for one stock."""
    rows = _quarters_for_stock(db, stock.id)
    if not rows:
        return False
    scenarios = all_scenario_fair_values([to_quarter(r) for r in rows], stock.is_financial)
    if not scenarios:
        return False

    param = db.get(StockParameter, stock.id)
    cp = param.current_price if param else None
    data: dict[str, Any] = {}
    for key, fv in scenarios.items():
        upside: float | None = None
        if fv is not None and cp is not None and cp > 0:
            upside = float((Decimal(str(fv)) - cp) / cp * Decimal(100))
        data[key] = {"fair_value": fv, "upside_pct": upside}

    existing = db.get(StockFairValue, stock.id)
    if existing is None:
        existing = StockFairValue(stock_id=stock.id)
        db.add(existing)
    existing.scenarios = data
    existing.current_price = cp
    existing.computed_at = _now()
    db.commit()
    return True


def financials_for_stock(db: Session, stock: Stock) -> bool:
    """Import new quarters (incremental) + fill historical closing prices."""
    if not stock.cik:
        try:
            lookup_and_save_cik(stock.symbol, db)
            db.refresh(stock)
        except Exception:  # noqa: BLE001 — handled by the missing-CIK check below
            db.rollback()

    latest_before = db.scalar(
        select(func.max(QuarterlyFinancial.period)).where(
            QuarterlyFinancial.stock_id == stock.id
        )
    )

    if not stock.cik:
        return False  # can't import SEC financials without a CIK
    preview = import_preview_edgar(stock.symbol, db)

    # Period strings are zero-padded "YYYY-QN" → lexical > is chronological.
    new_rows = [
        row for row in preview.rows if latest_before is None or row.period > latest_before
    ]
    if new_rows:
        bulk_upsert(
            stock.symbol,
            BulkUpsertRequest(
                rows=[
                    BulkUpsertRow(
                        period=row.period,
                        period_end_date=row.period_end_date,
                        raw_source=row.raw_source,
                        **row.fields,
                    )
                    for row in new_rows
                ],
                import_context=ImportContext(
                    parser_id=preview.parser_id,
                    source=preview.source,
                    statement=preview.statement,
                    caption=preview.caption,
                ),
            ),
            db,
        )

    # Historical closing prices — EoQ close for every quarter, not just new ones.
    closing = get_closing_prices(stock.symbol, periods=None, db=db)
    cp_rows = [
        BulkUpsertRow(period=p.period, closing_price=p.closing_price)
        for p in closing.prices
        if p.closing_price is not None
    ]
    if cp_rows:
        bulk_upsert(stock.symbol, BulkUpsertRequest(rows=cp_rows), db)
    return True


def prices_for_stock(db: Session, stock: Stock) -> bool:
    """Fetch + store current price and beta for one stock."""
    market = get_market_data(stock.symbol, db)
    param = db.get(StockParameter, stock.id)
    if param is None:
        param = StockParameter(stock_id=stock.id)
        db.add(param)
    price = _to_decimal(market.current_price)
    beta = _to_decimal(market.beta)
    if price is not None:
        param.current_price = price
    if beta is not None:
        param.beta = beta
    param.updated_at = _now()
    db.commit()
    return price is not None or beta is not None


def grades_for_stock(db: Session, stock: Stock, settings: Setting | None = None) -> bool:
    """Compute + store grades for one stock."""
    if settings is None:
        settings = db.get(Setting, SETTINGS_SINGLETON_ID)
    if settings is None:
        raise RuntimeError("Settings row missing — run `alembic upgrade head`.")

    rows = _quarters_for_stock(db, stock.id)
    if not rows:
        return False
    quarter_values = [to_quarter(r) for r in rows]
    param = db.get(StockParameter, stock.id)
    cp = param.current_price if param else None
    beta = param.beta if param else None
    merged = {**(settings.global_market_assumptions or {}), "current_price": cp, "beta": beta}
    shares = latest_shares_outstanding(quarter_values) or stock.shares_outstanding
    avg_fv = normal_fair_value(quarter_values, stock.is_financial)

    result = compute_grades(
        GradingInputs(
            quarters=quarter_values,
            parameters=merged,
            shares_outstanding=shares,
            current_price=cp,
            average_fair_value=_to_decimal(avg_fv),
            general_grade_weights=settings.general_grade_weights,
            sub_grade_weights=settings.sub_grade_weights,
            grade_thresholds=settings.grade_thresholds,
        )
    )

    existing = db.get(StockGrade, stock.id)
    if existing is None:
        existing = StockGrade(stock_id=stock.id)
        db.add(existing)
    existing.general = result.general
    existing.payload = grades_payload(result)
    existing.computed_at = _now()
    db.commit()
    return True


# Per-stock job registry — keys match the bulk job types.
PER_STOCK_JOBS: dict[str, Callable[[Session, Stock], bool]] = {
    "financials": financials_for_stock,
    "prices": prices_for_stock,
    "fair_values": fair_value_for_stock,
    "grades": grades_for_stock,
}


# ---------------------------------------------------------------------------
# Bulk drivers — run a per-stock primitive across the portfolio.
# ---------------------------------------------------------------------------


def _run_per_stock(
    db: Session,
    progress: Progress,
    handler: Callable[[Stock], bool],
    stocks: list[Stock] | None = None,
) -> None:
    """Drive `handler` across the given stocks (all stocks if none provided),
    tracking processed/succeeded/failed. Exceptions are caught, rolled back, and
    counted as failures so one bad stock never aborts the run.
    """
    if stocks is None:
        stocks = list(db.scalars(select(Stock).order_by(Stock.symbol)))
    progress(total=len(stocks), processed=0, succeeded=0, failed=0)
    succeeded = failed = 0
    for i, stock in enumerate(stocks):
        try:
            ok = handler(stock)
        except Exception:  # noqa: BLE001 — one bad stock must not kill the job
            logger.exception("Job handler failed for %s", stock.symbol)
            db.rollback()
            ok = False
        if ok:
            succeeded += 1
        else:
            failed += 1
        progress(processed=i + 1, succeeded=succeeded, failed=failed)


def _stocks_with_data(db: Session) -> list[Stock]:
    with_data = _stock_ids_with_quarters(db)
    return [
        s for s in db.scalars(select(Stock).order_by(Stock.symbol)) if s.id in with_data
    ]


def run_fair_values_job(db: Session, progress: Progress) -> None:
    # Only value stocks that have financials — empties aren't failures.
    _run_per_stock(
        db, progress, lambda s: fair_value_for_stock(db, s), _stocks_with_data(db)
    )


def run_financials_job(db: Session, progress: Progress) -> None:
    _run_per_stock(db, progress, lambda s: financials_for_stock(db, s))


def run_prices_job(db: Session, progress: Progress) -> None:
    _run_per_stock(db, progress, lambda s: prices_for_stock(db, s))


def run_grades_job(db: Session, progress: Progress) -> None:
    settings = db.get(Setting, SETTINGS_SINGLETON_ID)
    if settings is None:
        raise RuntimeError("Settings row missing — run `alembic upgrade head`.")
    # Only grade stocks that have financials — empties aren't failures.
    _run_per_stock(
        db, progress, lambda s: grades_for_stock(db, s, settings), _stocks_with_data(db)
    )
