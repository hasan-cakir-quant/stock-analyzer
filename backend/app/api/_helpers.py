"""Shared helpers for routers under /api."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Stock


def normalise_symbol(symbol: str) -> str:
    """Tickers are conventionally uppercase; canonicalise to avoid `aapl` ≠ `AAPL`."""
    return symbol.strip().upper()


def get_stock_or_404(db: Session, symbol: str) -> Stock:
    stock = db.scalar(select(Stock).where(Stock.symbol == normalise_symbol(symbol)))
    if stock is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock '{symbol}' not found.",
        )
    return stock
