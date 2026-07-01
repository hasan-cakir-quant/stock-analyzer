"""`snapshots` ORM model — immutable, soft-deletable analysis records."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.stock import Stock


class Snapshot(Base):
    __tablename__ = "snapshots"
    __table_args__ = (
        Index("ix_snapshots_stock_id", "stock_id"),
        Index("ix_snapshots_symbol", "symbol"),
        Index("ix_snapshots_created_at", "created_at"),
        Index(
            "ix_snapshots_active",
            "created_at",
            postgresql_where=text("soft_deleted_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    stock_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("stocks.id", ondelete="CASCADE"),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    note: Mapped[str | None] = mapped_column(Text)
    financials_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    parameters_used: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    settings_used: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    valuations: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    grades: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    growth_metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # MA-based valuation matrix frozen from the frontend at save time
    # (per method: latest MA4/8/12 fair values at the chosen scenario).
    ma_valuations: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    current_price_used: Mapped[Decimal | None] = mapped_column(Numeric)
    soft_deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    stock: Mapped[Stock] = relationship(back_populates="snapshots")
