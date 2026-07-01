"""In-process background-job runner.

No Celery/Redis — jobs run in a daemon thread with their own DB session, and
status/progress is tracked in the `job_runs` table so it survives across HTTP
requests and is visible from any page. One run per job type at a time.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from app.db.models import JobRun
from app.db.session import SessionLocal
from app.services.jobs import tasks

logger = logging.getLogger(__name__)

JOB_TYPES: tuple[str, ...] = ("fair_values", "financials", "prices", "grades")

_TASKS = {
    "fair_values": tasks.run_fair_values_job,
    "financials": tasks.run_financials_job,
    "prices": tasks.run_prices_job,
    "grades": tasks.run_grades_job,
}

# Serialises the "is one already running?" check + insert so two clicks can't
# both start the same job type.
_start_lock = threading.Lock()


class JobAlreadyRunningError(Exception):
    def __init__(self, job_type: str) -> None:
        self.job_type = job_type
        super().__init__(f"A '{job_type}' job is already running.")


def reconcile_orphaned_jobs() -> int:
    """Mark any lingering 'running' job_runs as failed.

    Jobs run in in-process threads, so a 'running' row can only survive a
    process exit if the run was interrupted (server restart, crash, or a
    short-lived script). Such a row is always orphaned — the thread that would
    finish it is gone — and would otherwise block the job type forever. Call
    once on startup. Returns how many rows were reconciled.
    """
    db = SessionLocal()
    try:
        orphaned = list(db.scalars(select(JobRun).where(JobRun.status == "running")))
        for run in orphaned:
            run.status = "failed"
            run.message = "Interrupted (server restart)."
            run.finished_at = datetime.now().astimezone()
        if orphaned:
            db.commit()
        return len(orphaned)
    finally:
        db.close()


def start_job(job_type: str) -> UUID:
    """Create a JobRun row and kick the task off in a daemon thread.

    Raises KeyError for an unknown job type, JobAlreadyRunningError if one is in
    flight. Returns the new run's id.
    """
    if job_type not in _TASKS:
        raise KeyError(job_type)

    with _start_lock:
        db = SessionLocal()
        try:
            running = db.scalar(
                select(JobRun.id).where(
                    JobRun.job_type == job_type, JobRun.status == "running"
                )
            )
            if running is not None:
                raise JobAlreadyRunningError(job_type)
            run = JobRun(
                job_type=job_type,
                status="running",
                started_at=datetime.now().astimezone(),
            )
            db.add(run)
            db.commit()
            db.refresh(run)
            run_id = run.id
        finally:
            db.close()

    threading.Thread(
        target=_execute, args=(job_type, run_id), name=f"job-{job_type}", daemon=True
    ).start()
    return run_id


def _execute(job_type: str, run_id: UUID) -> None:
    db = SessionLocal()
    run = db.get(JobRun, run_id)
    if run is None:
        db.close()
        return

    def progress(
        *,
        total: int | None = None,
        processed: int | None = None,
        succeeded: int | None = None,
        failed: int | None = None,
    ) -> None:
        if total is not None:
            run.total = total
        if processed is not None:
            run.processed = processed
        if succeeded is not None:
            run.succeeded = succeeded
        if failed is not None:
            run.failed = failed
        db.commit()

    try:
        _TASKS[job_type](db, progress)
        run.status = "success"
    except Exception as exc:  # noqa: BLE001 — record the failure, don't crash the thread
        logger.exception("Background job '%s' failed", job_type)
        db.rollback()
        run = db.get(JobRun, run_id)
        if run is not None:
            run.status = "failed"
            run.message = str(exc)[:1000]
    finally:
        if run is not None:
            run.finished_at = datetime.now().astimezone()
            db.commit()
        db.close()
