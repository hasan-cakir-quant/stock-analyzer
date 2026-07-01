"""Health-check router."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Stock
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe — returns ok when the API process is up."""
    return {"status": "ok"}


@router.get("/health/db")
def health_db(db: Session = Depends(get_db)) -> dict[str, object]:
    """Readiness probe — confirms the session dependency reaches Postgres."""
    stock_count = db.scalar(select(func.count()).select_from(Stock))
    return {"status": "ok", "stock_count": stock_count}
