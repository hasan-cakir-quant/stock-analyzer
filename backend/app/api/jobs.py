"""Background-jobs router — trigger jobs and read their latest status.

`POST /api/jobs/{job_type}/run` starts a job server-side (in a daemon thread)
and returns immediately; the job keeps running regardless of which page the user
has open. `GET /api/jobs` returns the latest run per job type for polling.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api._helpers import get_stock_or_404
from app.db.models import JobRun
from app.db.session import get_db
from app.services.jobs.runner import JOB_TYPES, JobAlreadyRunningError, start_job
from app.services.jobs.tasks import PER_STOCK_JOBS

router = APIRouter(prefix="/jobs", tags=["jobs"])
stock_router = APIRouter(prefix="/stocks/{symbol}", tags=["jobs"])


class JobRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_type: str
    status: str
    total: int
    processed: int
    succeeded: int
    failed: int
    message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


@router.get("", response_model=list[JobRunRead])
def list_latest_jobs(db: Session = Depends(get_db)) -> list[JobRun]:
    """Latest run per job type (the row backing each status card)."""
    out: list[JobRun] = []
    for job_type in JOB_TYPES:
        row = db.scalar(
            select(JobRun)
            .where(JobRun.job_type == job_type)
            .order_by(JobRun.created_at.desc())
            .limit(1)
        )
        if row is not None:
            out.append(row)
    return out


@router.post("/{job_type}/run", response_model=JobRunRead, status_code=status.HTTP_201_CREATED)
def run_job(job_type: str, db: Session = Depends(get_db)) -> JobRun:
    try:
        run_id = start_job(job_type)
    except KeyError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown job type '{job_type}'.",
        ) from err
    except JobAlreadyRunningError as err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err)) from err
    return db.get(JobRun, run_id)


class StockJobResult(BaseModel):
    symbol: str
    job_type: str
    ok: bool


@stock_router.post("/run/{job_type}", response_model=StockJobResult)
def run_stock_job(
    symbol: str, job_type: str, db: Session = Depends(get_db)
) -> StockJobResult:
    """Run a single job for ONE stock, synchronously (a single stock is quick).

    `ok` is False when the job had nothing to do (e.g. fair values / grades for a
    stock with no financials). External-source failures surface as a 502.
    """
    stock = get_stock_or_404(db, symbol)
    fn = PER_STOCK_JOBS.get(job_type)
    if fn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown job type '{job_type}'.",
        )
    try:
        ok = fn(db, stock)
    except HTTPException:
        raise
    except Exception as err:  # noqa: BLE001 — external sources / data issues
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(err)
        ) from err
    return StockJobResult(symbol=stock.symbol, job_type=job_type, ok=ok)
