"""Run-Full-Analysis endpoint.

`POST /api/stocks/{symbol}/analyze` runs valuations, grading, and growth
in one shot using whatever Parameter Panel state the user has open in
the browser. Nothing is persisted — the snapshot endpoint (Task 12) is
the path that freezes results.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api._helpers import get_stock_or_404
from app.db.models import QuarterlyFinancial, Setting
from app.db.models.setting import SETTINGS_SINGLETON_ID
from app.db.session import get_db
from app.schemas.stock_parameter import ValuationParameters
from app.services.analysis import run_full_analysis, to_quarter

router = APIRouter(prefix="/stocks/{symbol}", tags=["analysis"])


def _coerce_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _merged_parameters(
    body: ValuationParameters, defaults: dict[str, Any]
) -> dict[str, Any]:
    """User-supplied values win; missing keys fall back to global defaults."""
    user_values = body.model_dump(exclude_unset=True)
    merged: dict[str, Any] = dict(defaults)
    merged.update({k: v for k, v in user_values.items() if v is not None})
    return merged


@router.post("/analyze")
def analyze(
    symbol: str,
    payload: ValuationParameters,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    stock = get_stock_or_404(db, symbol)
    settings_row = db.get(Setting, SETTINGS_SINGLETON_ID)
    if settings_row is None:
        # Defensive — migrations seed this row.
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Settings row missing — run `alembic upgrade head`.",
        )

    rows = list(
        db.scalars(
            select(QuarterlyFinancial)
            .where(QuarterlyFinancial.stock_id == stock.id)
            .order_by(QuarterlyFinancial.period)
        )
    )
    quarters = [to_quarter(r) for r in rows]

    parameters = _merged_parameters(payload, settings_row.global_market_assumptions or {})
    current_price = _coerce_decimal(parameters.get("current_price"))

    return run_full_analysis(
        symbol=stock.symbol,
        quarters=quarters,
        parameters=parameters,
        shares_outstanding=stock.shares_outstanding,
        current_price=current_price,
        settings_general_grade_weights=settings_row.general_grade_weights,
        settings_sub_grade_weights=settings_row.sub_grade_weights,
        settings_grade_thresholds=settings_row.grade_thresholds,
        is_financial=stock.is_financial,
    )
