"""Settings router — read and full-replace the singleton settings row."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import Setting
from app.db.models.setting import SETTINGS_SINGLETON_ID
from app.db.session import get_db
from app.schemas.setting import SettingsRead, SettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])


def _get_singleton(db: Session) -> Setting:
    row = db.get(Setting, SETTINGS_SINGLETON_ID)
    if row is None:
        # Migrations seed this row — its absence means an incomplete bring-up.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Settings row missing — run `alembic upgrade head`.",
        )
    return row


@router.get("", response_model=SettingsRead)
def get_settings(db: Session = Depends(get_db)) -> Setting:
    return _get_singleton(db)


@router.put("", response_model=SettingsRead)
def update_settings(
    payload: SettingsUpdate, db: Session = Depends(get_db)
) -> Setting:
    row = _get_singleton(db)
    # mode="json" coerces Decimal -> str so the dicts are valid JSON for JSONB
    # storage. SettingsRead's Decimal fields parse strings back transparently.
    data = payload.model_dump(mode="json")
    row.general_grade_weights = data["general_grade_weights"]
    row.sub_grade_weights = data["sub_grade_weights"]
    row.grade_thresholds = data["grade_thresholds"]
    row.currency_format = data["currency_format"]
    row.global_market_assumptions = data["global_market_assumptions"]
    row.updated_at = datetime.now().astimezone()
    db.commit()
    db.refresh(row)
    return row
