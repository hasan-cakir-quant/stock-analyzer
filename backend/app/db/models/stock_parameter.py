"""`stock_parameters` ORM model — last-used Parameter Panel values per stock."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Numeric, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.stock import Stock


class StockParameter(Base):
    __tablename__ = "stock_parameters"

    stock_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("stocks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # Per-stock market data only. Valuation target multiples (P/E, EV/EBITDA)
    # are transient run-time inputs entered in the Valuations panel — they're
    # not persisted here; their defaults live in settings.global_market_assumptions.
    current_price: Mapped[Decimal | None] = mapped_column(Numeric)
    beta: Mapped[Decimal | None] = mapped_column(Numeric)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=lambda: datetime.now().astimezone(),
    )

    stock: Mapped[Stock] = relationship(back_populates="parameters")
