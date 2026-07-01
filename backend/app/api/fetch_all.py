"""One-shot data fetch — CIK, financials, closing prices, current price & beta.

`POST /api/stocks/{symbol}/fetch-all` orchestrates the individual fetch steps
behind a single button. Fundamentals come from SEC EDGAR (the stock's CIK is
resolved first if missing); prices come from the market-data provider.

Every step is best-effort: a failure in one (flaky external source) is captured
in the response rather than aborting the rest, so the user gets whatever did
resolve plus a per-step status they can act on.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api._helpers import get_stock_or_404
from app.api.cik import lookup_and_save_cik
from app.api.financials import (
    bulk_upsert,
    import_preview_edgar,
)
from app.api.market_data import get_closing_prices, get_market_data
from app.db.models import QuarterlyFinancial, StockParameter
from app.db.session import get_db
from app.schemas.financial_import import (
    BulkUpsertRequest,
    BulkUpsertRow,
    ImportContext,
)

router = APIRouter(prefix="/stocks/{symbol}", tags=["fetch-all"])


def _to_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None


@router.post("/fetch-all")
def fetch_all(symbol: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    stock = get_stock_or_404(db, symbol)
    source = "sec"
    steps: dict[str, Any] = {}

    # 1. CIK — required for the SEC/EDGAR fundamentals fetch.
    if stock.cik:
        steps["cik"] = {"ok": True, "value": stock.cik, "detail": "already set"}
    else:
        try:
            updated = lookup_and_save_cik(symbol, db)
            stock = get_stock_or_404(db, symbol)  # refresh after write
            steps["cik"] = {"ok": True, "value": updated.cik}
        except HTTPException as err:
            steps["cik"] = {"ok": False, "detail": str(err.detail)}

    # 2. Financials — import from SEC EDGAR.
    try:
        if not stock.cik:
            raise HTTPException(
                status_code=400,
                detail="No CIK available — can't import SEC financials.",
            )
        preview = import_preview_edgar(symbol, db)

        rows = [
            BulkUpsertRow(
                period=row.period,
                period_end_date=row.period_end_date,
                raw_source=row.raw_source,
                **row.fields,
            )
            for row in preview.rows
        ]
        resp = bulk_upsert(
            symbol,
            BulkUpsertRequest(
                rows=rows,
                import_context=ImportContext(
                    parser_id=preview.parser_id,
                    source=preview.source,
                    statement=preview.statement,
                    caption=preview.caption,
                ),
            ),
            db,
        )
        steps["financials"] = {"ok": True, "source": source, "written": resp.written}
    except HTTPException as err:
        steps["financials"] = {"ok": False, "source": source, "detail": str(err.detail)}

    # 3. Closing prices — end-of-quarter closes for every stored period.
    try:
        closing = get_closing_prices(symbol, periods=None, db=db)
        cp_rows = [
            BulkUpsertRow(period=p.period, closing_price=p.closing_price)
            for p in closing.prices
            if p.closing_price is not None
        ]
        if cp_rows:
            bulk_upsert(symbol, BulkUpsertRequest(rows=cp_rows), db)
        steps["closing_prices"] = {"ok": True, "written": len(cp_rows)}
    except HTTPException as err:
        steps["closing_prices"] = {"ok": False, "detail": str(err.detail)}

    # 4. Current price & beta — saved onto the per-stock parameters row.
    try:
        market = get_market_data(symbol, db)
        param_row = db.get(StockParameter, stock.id)
        if param_row is None:
            param_row = StockParameter(stock_id=stock.id)
            db.add(param_row)
        price = _to_decimal(market.current_price)
        beta = _to_decimal(market.beta)
        if price is not None:
            param_row.current_price = price
        if beta is not None:
            param_row.beta = beta
        param_row.updated_at = datetime.now().astimezone()
        db.commit()
        steps["market_data"] = {
            "ok": True,
            "current_price": market.current_price,
            "beta": market.beta,
        }
    except HTTPException as err:
        steps["market_data"] = {"ok": False, "detail": str(err.detail)}

    return {"symbol": stock.symbol, "source": source, "steps": steps}


@router.post("/refresh")
def refresh(symbol: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Incremental top-up — add only quarters newer than the latest stored one.

    Unlike `fetch-all` (which re-imports every quarter), refresh imports from
    SEC EDGAR but keeps only periods strictly after the latest period already in
    the database, writes those, fetches *their* end-of-quarter closing prices,
    and refreshes the live current price & beta. If the stock has no financials
    yet, every imported quarter counts as new (a full first pull).

    Best-effort per step, mirroring `fetch-all`.
    """
    stock = get_stock_or_404(db, symbol)
    source = "sec"
    steps: dict[str, Any] = {}

    latest_before = db.scalar(
        select(func.max(QuarterlyFinancial.period)).where(
            QuarterlyFinancial.stock_id == stock.id
        )
    )

    # 1. CIK — required for the SEC/EDGAR fundamentals fetch.
    if stock.cik:
        steps["cik"] = {"ok": True, "value": stock.cik, "detail": "already set"}
    else:
        try:
            updated = lookup_and_save_cik(symbol, db)
            stock = get_stock_or_404(db, symbol)  # refresh after write
            steps["cik"] = {"ok": True, "value": updated.cik}
        except HTTPException as err:
            steps["cik"] = {"ok": False, "detail": str(err.detail)}

    # 2. Financials — import, then keep only periods newer than latest_before.
    new_periods: list[str] = []
    try:
        if not stock.cik:
            raise HTTPException(
                status_code=400,
                detail="No CIK available — can't import SEC financials.",
            )
        preview = import_preview_edgar(symbol, db)

        # Period strings are zero-padded "YYYY-QN", so lexical > is chronological.
        new_preview_rows = [
            row
            for row in preview.rows
            if latest_before is None or row.period > latest_before
        ]
        rows = [
            BulkUpsertRow(
                period=row.period,
                period_end_date=row.period_end_date,
                raw_source=row.raw_source,
                **row.fields,
            )
            for row in new_preview_rows
        ]
        if rows:
            bulk_upsert(
                symbol,
                BulkUpsertRequest(
                    rows=rows,
                    import_context=ImportContext(
                        parser_id=preview.parser_id,
                        source=preview.source,
                        statement=preview.statement,
                        caption=preview.caption,
                    ),
                ),
                db,
            )
        new_periods = [row.period for row in new_preview_rows]
        all_periods = [p for p in [latest_before, *new_periods] if p]
        steps["financials"] = {
            "ok": True,
            "source": source,
            "written": len(rows),
            "new_periods": new_periods,
            "latest_before": latest_before,
            "latest_after": max(all_periods) if all_periods else None,
        }
    except HTTPException as err:
        steps["financials"] = {"ok": False, "source": source, "detail": str(err.detail)}

    # 3. Closing prices — only for the newly added quarters.
    if new_periods:
        try:
            closing = get_closing_prices(symbol, periods=new_periods, db=db)
            cp_rows = [
                BulkUpsertRow(period=p.period, closing_price=p.closing_price)
                for p in closing.prices
                if p.closing_price is not None
            ]
            if cp_rows:
                bulk_upsert(symbol, BulkUpsertRequest(rows=cp_rows), db)
            steps["closing_prices"] = {"ok": True, "written": len(cp_rows)}
        except HTTPException as err:
            steps["closing_prices"] = {"ok": False, "detail": str(err.detail)}
    else:
        steps["closing_prices"] = {
            "ok": True,
            "written": 0,
            "detail": "no new quarters",
        }

    # 4. Current price & beta — full top-up onto the per-stock parameters row.
    try:
        market = get_market_data(symbol, db)
        param_row = db.get(StockParameter, stock.id)
        if param_row is None:
            param_row = StockParameter(stock_id=stock.id)
            db.add(param_row)
        price = _to_decimal(market.current_price)
        beta = _to_decimal(market.beta)
        if price is not None:
            param_row.current_price = price
        if beta is not None:
            param_row.beta = beta
        param_row.updated_at = datetime.now().astimezone()
        db.commit()
        steps["market_data"] = {
            "ok": True,
            "current_price": market.current_price,
            "beta": market.beta,
        }
    except HTTPException as err:
        steps["market_data"] = {"ok": False, "detail": str(err.detail)}

    return {"symbol": stock.symbol, "source": source, "steps": steps}
