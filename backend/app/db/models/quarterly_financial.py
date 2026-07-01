"""`quarterly_financials` ORM model."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Numeric, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.stock import Stock


class QuarterlyFinancial(Base):
    __tablename__ = "quarterly_financials"
    __table_args__ = (
        UniqueConstraint("stock_id", "period", name="uq_quarterly_financials_stock_period"),
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
        index=True,
    )
    period: Mapped[str] = mapped_column(Text, nullable=False)
    period_end_date: Mapped[date | None] = mapped_column(Date)

    # Income statement
    revenue: Mapped[Decimal | None] = mapped_column(Numeric)
    cogs: Mapped[Decimal | None] = mapped_column(Numeric)
    gross_profit: Mapped[Decimal | None] = mapped_column(Numeric)
    operating_expenses: Mapped[Decimal | None] = mapped_column(Numeric)
    operating_income: Mapped[Decimal | None] = mapped_column(Numeric)
    interest_expense: Mapped[Decimal | None] = mapped_column(Numeric)
    pretax_income: Mapped[Decimal | None] = mapped_column(Numeric)
    net_income: Mapped[Decimal | None] = mapped_column(Numeric)
    eps_basic: Mapped[Decimal | None] = mapped_column(Numeric)
    eps_diluted: Mapped[Decimal | None] = mapped_column(Numeric)
    ebitda: Mapped[Decimal | None] = mapped_column(Numeric)
    shares_outstanding_diluted: Mapped[Decimal | None] = mapped_column(Numeric)

    # Balance sheet
    cash_and_equivalents: Mapped[Decimal | None] = mapped_column(Numeric)
    short_term_investments: Mapped[Decimal | None] = mapped_column(Numeric)
    total_current_assets: Mapped[Decimal | None] = mapped_column(Numeric)
    total_assets: Mapped[Decimal | None] = mapped_column(Numeric)
    short_term_debt: Mapped[Decimal | None] = mapped_column(Numeric)
    total_current_liabilities: Mapped[Decimal | None] = mapped_column(Numeric)
    long_term_debt: Mapped[Decimal | None] = mapped_column(Numeric)
    total_liabilities: Mapped[Decimal | None] = mapped_column(Numeric)
    total_equity: Mapped[Decimal | None] = mapped_column(Numeric)
    inventory: Mapped[Decimal | None] = mapped_column(Numeric)
    receivables: Mapped[Decimal | None] = mapped_column(Numeric)

    # Cash flow
    operating_cash_flow: Mapped[Decimal | None] = mapped_column(Numeric)
    capex: Mapped[Decimal | None] = mapped_column(Numeric)
    free_cash_flow: Mapped[Decimal | None] = mapped_column(Numeric)
    dividends_paid: Mapped[Decimal | None] = mapped_column(Numeric)
    stock_buybacks: Mapped[Decimal | None] = mapped_column(Numeric)

    # Market data
    closing_price: Mapped[Decimal | None] = mapped_column(Numeric)

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=lambda: datetime.now().astimezone(),
    )

    stock: Mapped[Stock] = relationship(back_populates="financials")
