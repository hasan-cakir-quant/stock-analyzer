"""Imports router — exposes the parser registry so the UI can populate the
source dropdown before the user uploads anything.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.financial_import import ImportSource
from app.services.imports import available_parsers

router = APIRouter(prefix="/imports", tags=["imports"])


@router.get("/sources", response_model=list[ImportSource])
def list_sources() -> list[ImportSource]:
    return [
        ImportSource(id=p.id, source=p.source, statement=p.statement, label=p.label)
        for p in available_parsers()
    ]
