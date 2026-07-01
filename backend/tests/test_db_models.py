"""Smoke tests for the SQLAlchemy session and Stock model."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Stock


def test_insert_and_read_stock(db_session: Session) -> None:
    stock = Stock(
        symbol="AAPL",
        currency="USD",
        shares_outstanding=Decimal("15500000000"),
        notes="Test stock",
    )
    db_session.add(stock)
    db_session.flush()

    assert stock.id is not None
    assert stock.created_at is not None
    assert stock.updated_at is not None

    fetched = db_session.scalar(select(Stock).where(Stock.symbol == "AAPL"))
    assert fetched is not None
    assert fetched.id == stock.id
    assert fetched.currency == "USD"
    assert fetched.shares_outstanding == Decimal("15500000000")
    assert fetched.notes == "Test stock"
