"""Stocks router — CRUD for tracked equities."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api._helpers import get_stock_or_404, normalise_symbol
from app.db.models import Stock
from app.db.session import get_db
from app.schemas.stock import StockCreate, StockRead, StockUpdate
from app.services.providers import ProviderError, wikipedia_provider

router = APIRouter(prefix="/stocks", tags=["stocks"])


class SeedSp500Result(BaseModel):
    total: int  # symbols found on Wikipedia (de-duplicated)
    created: int  # new stock shells inserted
    skipped: int  # symbols that were already tracked
    created_symbols: list[str]


@router.post("/seed-sp500", response_model=SeedSp500Result)
def seed_sp500(db: Session = Depends(get_db)) -> SeedSp500Result:
    """Create an empty USD stock shell for every current S&P 500 constituent.

    Pulls the live ticker list from Wikipedia and inserts any symbols not
    already tracked (category "S&P 500"). No financial or price data is
    fetched — use the Data screen's Refresh to populate each stock afterwards.
    """
    try:
        symbols = wikipedia_provider.get_constituents("sp500")
    except ProviderError as err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(err)
        ) from err

    existing = set(db.scalars(select(Stock.symbol)))
    created_symbols: list[str] = []
    for raw in symbols:
        sym = normalise_symbol(raw)
        if sym in existing:
            continue
        existing.add(sym)  # guard against any in-list duplicates after normalising
        db.add(Stock(symbol=sym, currency="USD", category="S&P 500"))
        created_symbols.append(sym)

    db.commit()
    return SeedSp500Result(
        total=len(symbols),
        created=len(created_symbols),
        skipped=len(symbols) - len(created_symbols),
        created_symbols=created_symbols,
    )


@router.post("", response_model=StockRead, status_code=status.HTTP_201_CREATED)
def create_stock(payload: StockCreate, db: Session = Depends(get_db)) -> Stock:
    stock = Stock(
        symbol=normalise_symbol(payload.symbol),
        currency=payload.currency,
        shares_outstanding=payload.shares_outstanding,
        notes=payload.notes,
        category=payload.category,
        is_financial=payload.is_financial,
        units_note=payload.units_note,
        cik=payload.cik,
    )
    db.add(stock)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Stock '{stock.symbol}' already exists.",
        ) from None
    db.refresh(stock)
    return stock


@router.get("", response_model=list[StockRead])
def list_stocks(db: Session = Depends(get_db)) -> list[Stock]:
    return list(db.scalars(select(Stock).order_by(Stock.symbol)))


@router.get("/{symbol}", response_model=StockRead)
def get_stock(symbol: str, db: Session = Depends(get_db)) -> Stock:
    return get_stock_or_404(db, symbol)


@router.patch("/{symbol}", response_model=StockRead)
def update_stock(
    symbol: str, payload: StockUpdate, db: Session = Depends(get_db)
) -> Stock:
    stock = get_stock_or_404(db, symbol)
    # Only fields the client actually sent; absent keys leave the column alone.
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(stock, field, value)
    stock.updated_at = datetime.now().astimezone()
    db.commit()
    db.refresh(stock)
    return stock


@router.delete("/{symbol}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stock(symbol: str, db: Session = Depends(get_db)) -> None:
    """Delete a tracked stock and everything tied to it. The FK cascades
    (ON DELETE CASCADE) drop the stock's financials, parameters, snapshots,
    and import archives."""
    stock = get_stock_or_404(db, symbol)
    db.delete(stock)
    db.commit()
