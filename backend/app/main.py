"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    analyze,
    cik,
    data_availability,
    fetch_all,
    financials,
    health,
    imports as imports_router,
    jobs as jobs_router,
    market_data,
    parameters,
    portfolio,
    settings as settings_router,
    snapshots,
    stocks,
)
from app.core.config import get_settings
from app.services.jobs.runner import reconcile_orphaned_jobs

settings = get_settings()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # In-process jobs can't survive a restart — clear any orphaned 'running'
    # rows so a crashed/restarted run doesn't show "Running" forever.
    reconciled = reconcile_orphaned_jobs()
    if reconciled:
        logger.info("Reconciled %d orphaned background job(s) on startup.", reconciled)
    yield


app = FastAPI(
    title="Stock Analyzer API",
    description="Personal stock analysis application backend.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers live under the /api prefix. New routers register here.
app.include_router(health.router, prefix="/api")
app.include_router(settings_router.router, prefix="/api")
app.include_router(stocks.router, prefix="/api")
app.include_router(financials.router, prefix="/api")
app.include_router(imports_router.router, prefix="/api")
app.include_router(parameters.router, prefix="/api")
app.include_router(market_data.router, prefix="/api")
app.include_router(cik.router, prefix="/api")
app.include_router(analyze.router, prefix="/api")
app.include_router(fetch_all.router, prefix="/api")
app.include_router(data_availability.router, prefix="/api")
app.include_router(jobs_router.router, prefix="/api")
app.include_router(jobs_router.stock_router, prefix="/api")
app.include_router(snapshots.router, prefix="/api")
app.include_router(snapshots.cross_router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
