"""`settings` ORM model — singleton row holding all global configuration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, Integer, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# The row is a singleton — `id` is always 1; the check constraint enforces it.
SETTINGS_SINGLETON_ID = 1


class Setting(Base):
    __tablename__ = "settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_settings_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    general_grade_weights: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    sub_grade_weights: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    grade_thresholds: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    currency_format: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    global_market_assumptions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=lambda: datetime.now().astimezone(),
    )
