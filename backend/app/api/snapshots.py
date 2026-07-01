"""Snapshots router — creation, listing, detail, comparison, and delete.

Two routers live here:
  * `router` — `/stocks/{symbol}/snapshots`  (per-stock POST + GET list)
  * `cross_router` — `/snapshots`             (cross-stock list, detail, compare, delete)
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import Numeric, cast, select
from sqlalchemy.orm import Session

from app.api._helpers import get_stock_or_404
from app.db.models import QuarterlyFinancial, Setting, Snapshot
from app.db.models.setting import SETTINGS_SINGLETON_ID
from app.db.session import get_db
from app.schemas.quarterly_financial import QuarterlyFinancialRead
from app.schemas.setting import SettingsRead
from app.schemas.snapshot import (
    SnapshotCreate,
    SnapshotListItem,
    SnapshotRead,
)
from app.schemas.stock_parameter import ValuationParameters
from app.services.analysis import run_full_analysis, to_quarter

router = APIRouter(prefix="/stocks/{symbol}/snapshots", tags=["snapshots"])
cross_router = APIRouter(prefix="/snapshots", tags=["snapshots"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _settings_or_500(db: Session) -> Setting:
    row = db.get(Setting, SETTINGS_SINGLETON_ID)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Settings row missing — run `alembic upgrade head`.",
        )
    return row


def _coerce_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _merged_parameters(
    body: ValuationParameters, defaults: dict[str, Any]
) -> dict[str, Any]:
    user_values = body.model_dump(exclude_unset=True)
    merged: dict[str, Any] = dict(defaults)
    merged.update({k: v for k, v in user_values.items() if v is not None})
    return merged


def _ma_valuations_summary(
    ma_valuations: dict[str, Any] | None, current_price: Decimal | None
) -> dict[str, Any] | None:
    """Blend the MA-valuation matrix into one summary.

    The headline fair value is the *value-area mean* — the average of the
    central-70% band of all fair-value cells (each method × MA4/MA8/MA12) at the
    snapshot's scenario. Trimming the outlier tails makes it robust to one
    method blowing out (e.g. EV/FCF). The client computes the value area (so it
    matches the distribution chart exactly) and passes it as
    `ma_valuations["value_area"]`; we read its `mean`. For older clients that
    don't send a value area, we fall back to the median of every cell.

    `average` and `median` both carry the headline value so existing readers
    (snapshot header, portfolio "fair value" column) pick it up unchanged.
    Returns None when no MA matrix was supplied.
    """
    if not ma_valuations:
        return None

    fairs: list[float] = []
    for method in ma_valuations.get("methods", []) or []:
        for window in method.get("windows", []) or []:
            fv = window.get("fair_value")
            if fv is None:
                continue
            try:
                fairs.append(float(fv))
            except (TypeError, ValueError):
                continue

    if not fairs:
        return {"average": None, "median": None, "current_price": None, "upside_pct": None}

    headline: float | None = None
    value_area = ma_valuations.get("value_area")
    if isinstance(value_area, dict) and value_area.get("mean") is not None:
        try:
            headline = float(value_area["mean"])
        except (TypeError, ValueError):
            headline = None
    if headline is None:
        # Fallback for snapshots saved before the value area existed.
        fairs.sort()
        n = len(fairs)
        headline = fairs[n // 2] if n % 2 else (fairs[n // 2 - 1] + fairs[n // 2]) / 2

    cp = float(current_price) if current_price is not None else None
    upside = ((headline - cp) / cp * 100) if cp else None
    return {
        "average": headline,
        "median": headline,
        "current_price": cp,
        "upside_pct": upside,
    }


def _to_list_item(s: Snapshot) -> dict[str, Any]:
    """Pick the columns needed for a snapshot list, plus the denormalised
    general grade and average fair value pulled out of the JSONB blobs.
    """
    grades = s.grades or {}
    summary = (s.valuations or {}).get("summary", {})
    return {
        "id": s.id,
        "stock_id": s.stock_id,
        "symbol": s.symbol,
        "created_at": s.created_at,
        "note": s.note,
        "current_price_used": s.current_price_used,
        "soft_deleted_at": s.soft_deleted_at,
        "general_grade": grades.get("general"),
        "average_fair_value": summary.get("average"),
    }


def _get_snapshot_or_404(db: Session, snapshot_id: UUID) -> Snapshot:
    snap = db.get(Snapshot, snapshot_id)
    if snap is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot '{snapshot_id}' not found.",
        )
    return snap


# ---------------------------------------------------------------------------
# Per-stock router
# ---------------------------------------------------------------------------


@router.post("", response_model=SnapshotRead, status_code=status.HTTP_201_CREATED)
def create_snapshot(
    symbol: str, payload: SnapshotCreate, db: Session = Depends(get_db)
) -> Snapshot:
    stock = get_stock_or_404(db, symbol)
    settings_row = _settings_or_500(db)

    rows = list(
        db.scalars(
            select(QuarterlyFinancial)
            .where(QuarterlyFinancial.stock_id == stock.id)
            .order_by(QuarterlyFinancial.period)
        )
    )

    parameters = _merged_parameters(
        payload.parameters, settings_row.global_market_assumptions or {}
    )
    current_price = _coerce_decimal(parameters.get("current_price"))

    analysis = run_full_analysis(
        symbol=stock.symbol,
        quarters=[to_quarter(r) for r in rows],
        parameters=parameters,
        shares_outstanding=stock.shares_outstanding,
        current_price=current_price,
        settings_general_grade_weights=settings_row.general_grade_weights,
        settings_sub_grade_weights=settings_row.sub_grade_weights,
        settings_grade_thresholds=settings_row.grade_thresholds,
        is_financial=stock.is_financial,
    )

    # The MA valuation (the scenario the user picked) is the source of truth for
    # the snapshot's fair value — replace the default-multiple model valuations.
    ma_summary = _ma_valuations_summary(payload.ma_valuations, current_price)
    if ma_summary is not None:
        analysis["valuations"] = {"models": {}, "summary": ma_summary}

    financials_snapshot = [
        QuarterlyFinancialRead.model_validate(r).model_dump(mode="json") for r in rows
    ]
    parameters_used = ValuationParameters.model_validate(parameters).model_dump(mode="json")
    settings_used = SettingsRead.model_validate(settings_row).model_dump(mode="json")

    snapshot = Snapshot(
        stock_id=stock.id,
        symbol=stock.symbol,
        # Set created_at explicitly so back-to-back snapshots inside one
        # transaction get distinct timestamps. PostgreSQL's now() returns
        # the transaction start, which collides for rapid successive saves.
        created_at=datetime.now().astimezone(),
        note=payload.note,
        financials_snapshot=financials_snapshot,
        parameters_used=parameters_used,
        settings_used=settings_used,
        valuations=analysis["valuations"],
        grades=analysis["grades"],
        growth_metrics=analysis["growth"],
        ma_valuations=payload.ma_valuations,
        current_price_used=current_price,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


@router.get("", response_model=list[SnapshotListItem])
def list_stock_snapshots(
    symbol: str,
    include_deleted: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    stock = get_stock_or_404(db, symbol)
    stmt = (
        select(Snapshot)
        .where(Snapshot.stock_id == stock.id)
        .order_by(Snapshot.created_at.desc())
    )
    if not include_deleted:
        stmt = stmt.where(Snapshot.soft_deleted_at.is_(None))
    return [_to_list_item(s) for s in db.scalars(stmt)]


# ---------------------------------------------------------------------------
# Cross-stock router
# ---------------------------------------------------------------------------


@cross_router.get("", response_model=list[SnapshotListItem])
def list_snapshots(
    symbol: str | None = Query(default=None, description="Substring match (case-insensitive)."),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    grade_min: Decimal | None = Query(default=None, ge=0, le=100),
    grade_max: Decimal | None = Query(default=None, ge=0, le=100),
    include_deleted: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    stmt = select(Snapshot).order_by(Snapshot.created_at.desc())

    if not include_deleted:
        stmt = stmt.where(Snapshot.soft_deleted_at.is_(None))
    if symbol:
        stmt = stmt.where(Snapshot.symbol.ilike(f"%{symbol}%"))
    if created_from is not None:
        stmt = stmt.where(Snapshot.created_at >= created_from)
    if created_to is not None:
        stmt = stmt.where(Snapshot.created_at <= created_to)

    if grade_min is not None or grade_max is not None:
        # Filter on the JSONB-encoded general grade. JSONB null .astext is
        # SQL NULL → the row is excluded by the comparison, which is the
        # right behaviour for incomplete snapshots.
        general_grade = cast(Snapshot.grades["general"].astext, Numeric)
        if grade_min is not None:
            stmt = stmt.where(general_grade >= grade_min)
        if grade_max is not None:
            stmt = stmt.where(general_grade <= grade_max)

    return [_to_list_item(s) for s in db.scalars(stmt)]


@cross_router.get("/{snapshot_id}", response_model=SnapshotRead)
def get_snapshot(snapshot_id: UUID, db: Session = Depends(get_db)) -> Snapshot:
    return _get_snapshot_or_404(db, snapshot_id)


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------


class SnapshotCompareRequest(BaseModel):
    snapshot_id_a: UUID
    snapshot_id_b: UUID


def _delta(a: Any, b: Any) -> float | None:
    """Return b - a as a float, or None if either side isn't a finite number."""
    try:
        if a is None or b is None:
            return None
        return float(b) - float(a)
    except (TypeError, ValueError):
        return None


def _build_deltas(a: Snapshot, b: Snapshot) -> dict[str, Any]:
    """Compute b − a across every numeric field surfaced in the UI."""
    grades_a, grades_b = a.grades or {}, b.grades or {}
    summary_a = (a.valuations or {}).get("summary", {})
    summary_b = (b.valuations or {}).get("summary", {})
    models_a = (a.valuations or {}).get("models", {})
    models_b = (b.valuations or {}).get("models", {})
    growth_a = (a.growth_metrics or {}).get("metrics", {})
    growth_b = (b.growth_metrics or {}).get("metrics", {})
    params_a = a.parameters_used or {}
    params_b = b.parameters_used or {}

    sub_grades = {
        name: _delta(
            (grades_a.get("sub_grades", {}).get(name) or {}).get("score"),
            (grades_b.get("sub_grades", {}).get(name) or {}).get("score"),
        )
        for name in sorted(
            set(grades_a.get("sub_grades", {})) | set(grades_b.get("sub_grades", {}))
        )
    }
    valuation_models = {
        name: _delta(
            (models_a.get(name) or {}).get("fair_value"),
            (models_b.get(name) or {}).get("fair_value"),
        )
        for name in sorted(set(models_a) | set(models_b))
    }
    growth = {
        metric: {
            horizon: _delta(
                (growth_a.get(metric) or {}).get(horizon),
                (growth_b.get(metric) or {}).get(horizon),
            )
            for horizon in sorted(
                set((growth_a.get(metric) or {}).keys())
                | set((growth_b.get(metric) or {}).keys())
            )
        }
        for metric in sorted(set(growth_a) | set(growth_b))
    }
    parameters = {
        key: _delta(params_a.get(key), params_b.get(key))
        for key in sorted(set(params_a) | set(params_b))
    }

    return {
        "general_grade": _delta(grades_a.get("general"), grades_b.get("general")),
        "average_fair_value": _delta(summary_a.get("average"), summary_b.get("average")),
        "median_fair_value": _delta(summary_a.get("median"), summary_b.get("median")),
        "current_price": _delta(
            summary_a.get("current_price"), summary_b.get("current_price")
        ),
        "upside_pct": _delta(summary_a.get("upside_pct"), summary_b.get("upside_pct")),
        "sub_grades": sub_grades,
        "valuation_models": valuation_models,
        "growth": growth,
        "parameters": parameters,
    }


class SnapshotCompareResponse(BaseModel):
    a: SnapshotRead
    b: SnapshotRead
    deltas: dict[str, Any]


@cross_router.post("/compare", response_model=SnapshotCompareResponse)
def compare_snapshots(
    payload: SnapshotCompareRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    a = _get_snapshot_or_404(db, payload.snapshot_id_a)
    b = _get_snapshot_or_404(db, payload.snapshot_id_b)
    return {"a": a, "b": b, "deltas": _build_deltas(a, b)}


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@cross_router.delete("/{snapshot_id}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_snapshot(snapshot_id: UUID, db: Session = Depends(get_db)) -> None:
    snap = _get_snapshot_or_404(db, snapshot_id)
    if snap.soft_deleted_at is None:
        snap.soft_deleted_at = datetime.now().astimezone()
        db.commit()
    # Idempotent — already-deleted snapshots return 204 too.


@cross_router.delete("/{snapshot_id}/hard", status_code=status.HTTP_204_NO_CONTENT)
def hard_delete_snapshot(snapshot_id: UUID, db: Session = Depends(get_db)) -> None:
    snap = _get_snapshot_or_404(db, snapshot_id)
    if snap.soft_deleted_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Snapshot must be soft-deleted before hard-delete.",
        )
    db.delete(snap)
    db.commit()
