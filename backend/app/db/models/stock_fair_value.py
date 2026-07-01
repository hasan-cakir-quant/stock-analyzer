"""`stock_fair_values` ORM model — latest MA fair value per scenario, per stock."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import ForeignKey, Numeric, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.stock import Stock


class StockFairValue(Base):
    __tablename__ = "stock_fair_values"

    stock_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("stocks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # { scenario_key: {"fair_value": float|None, "upside_pct": float|None}, ... }
    scenarios: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    current_price: Mapped[Decimal | None] = mapped_column(Numeric)
    computed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    stock: Mapped[Stock] = relationship()
