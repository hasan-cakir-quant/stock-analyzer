"""`financial_imports` — raw payload of every parsed source upload.

One row per (stock, source, statement, period). The payload preserves
every label the source ships (including ones we don't have a schema
column for) keyed by the source's own label, in source units. Re-imports
overwrite the row; the unique constraint enforces the (stock, source,
statement, period) scope.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.stock import Stock


class FinancialImport(Base):
    __tablename__ = "financial_imports"
    __table_args__ = (
        UniqueConstraint(
            "stock_id",
            "source",
            "statement",
            "period",
            name="uq_financial_imports_scope",
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
        index=True,
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    parser_id: Mapped[str] = mapped_column(Text, nullable=False)
    period: Mapped[str] = mapped_column(Text, nullable=False)
    period_end_date: Mapped[date | None] = mapped_column(Date)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    source_caption: Mapped[str | None] = mapped_column(Text)
    imported_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    stock: Mapped[Stock] = relationship()
