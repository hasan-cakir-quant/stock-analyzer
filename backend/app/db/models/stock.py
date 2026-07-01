"""`stocks` ORM model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Numeric, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.quarterly_financial import QuarterlyFinancial
    from app.db.models.snapshot import Snapshot
    from app.db.models.stock_parameter import StockParameter


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    symbol: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False)
    shares_outstanding: Mapped[Decimal | None] = mapped_column(Numeric)
    notes: Mapped[str | None] = mapped_column(Text)
    # Free-text grouping label shown/edited on the portfolio page
    # (e.g. "Tech", "Watchlist", "BIST"). Null = uncategorized.
    category: Mapped[str | None] = mapped_column(Text)
    # Bank / financial institution — EV-based valuations don't apply
    # (deposits aren't debt, reserves aren't excess cash), so they opt out.
    is_financial: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # Free-text reminder of the units the financial values are entered in
    # (e.g. "Quarterly Data | Millions of US $ except per share data").
    # Auto-filled by the HTML importer; editable via Edit Metadata.
    units_note: Mapped[str | None] = mapped_column(Text)
    # SEC EDGAR Central Index Key, stored as the canonical zero-padded
    # 10-digit string (e.g. "0000320193"). Resolved on demand via the
    # Fetch CIK button; users may also override it manually.
    cik: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=lambda: datetime.now().astimezone(),
    )

    financials: Mapped[list[QuarterlyFinancial]] = relationship(
        back_populates="stock",
        cascade="all, delete-orphan",
    )
    parameters: Mapped[StockParameter | None] = relationship(
        back_populates="stock",
        uselist=False,
        cascade="all, delete-orphan",
    )
    snapshots: Mapped[list[Snapshot]] = relationship(
        back_populates="stock",
        cascade="all, delete-orphan",
    )
