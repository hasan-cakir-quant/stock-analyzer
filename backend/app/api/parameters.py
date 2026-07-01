"""Stock-parameters router — last-used market-data values per stock (FR-3.6.3).

GET returns the per-stock `current_price` / `beta` (null when never saved). PUT
upserts and uses `exclude_unset` so a single-cell auto-save only touches one
column. Valuation target multiples are no longer stored here — they're transient
run-time inputs whose defaults live in `settings.global_market_assumptions`.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api._helpers import get_stock_or_404
from app.db.models import StockParameter
from app.db.session import get_db
from app.schemas.stock_parameter import StockParameterRead, StockParameterUpsert

router = APIRouter(prefix="/stocks/{symbol}/parameters", tags=["parameters"])


def _payload(stock_id, row: StockParameter | None) -> dict[str, object]:
    base: dict[str, object] = {"stock_id": stock_id, "updated_at": None}
    for field in StockParameterUpsert.model_fields:
        base[field] = getattr(row, field, None) if row is not None else None
    if row is not None:
        base["updated_at"] = row.updated_at
    return base


@router.get("", response_model=StockParameterRead)
def get_parameters(symbol: str, db: Session = Depends(get_db)) -> dict[str, object]:
    stock = get_stock_or_404(db, symbol)
    row = db.get(StockParameter, stock.id)
    return _payload(stock.id, row)


@router.put("", response_model=StockParameterRead)
def upsert_parameters(
    symbol: str, payload: StockParameterUpsert, db: Session = Depends(get_db)
) -> dict[str, object]:
    stock = get_stock_or_404(db, symbol)
    row = db.get(StockParameter, stock.id)
    if row is None:
        row = StockParameter(stock_id=stock.id)
        db.add(row)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)

    row.updated_at = datetime.now().astimezone()
    db.commit()
    db.refresh(row)
    return _payload(stock.id, row)
