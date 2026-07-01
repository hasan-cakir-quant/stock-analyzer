"""CIK lookup router — resolves a stock's SEC EDGAR CIK and persists it.

`POST /api/stocks/{symbol}/cik/lookup` is intentionally state-changing:
it both reads EDGAR and writes the result to `stocks.cik`. Users who
just want to see a candidate without persisting can still hand-edit
the value via the Edit Metadata dialog afterwards.
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api._helpers import get_stock_or_404
from app.db.session import get_db
from app.schemas.stock import StockRead
from app.services.providers import SecLookupError, sec_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stocks/{symbol}/cik", tags=["cik"])


@router.post("/lookup", response_model=StockRead)
def lookup_and_save_cik(symbol: str, db: Session = Depends(get_db)) -> StockRead:
    stock = get_stock_or_404(db, symbol)

    try:
        cik = sec_provider.lookup_cik(stock.symbol)
    except SecLookupError as err:
        logger.warning("SEC EDGAR lookup failed for %s: %s", stock.symbol, err)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(err),
        ) from err

    if cik is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SEC EDGAR has no CIK for '{stock.symbol}'.",
        )

    stock.cik = cik
    stock.updated_at = datetime.now().astimezone()
    db.commit()
    db.refresh(stock)
    return StockRead.model_validate(stock)
