"""Schemas for the HTML-import feature: source listing, preview, and bulk upsert."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.schemas.quarterly_financial import QuarterlyFinancialUpsert


class ImportSource(BaseModel):
    """One entry in the parser dropdown."""

    id: str
    source: str
    statement: str  # "income" | "balance" | "cashflow"
    label: str


class ImportRowPreview(BaseModel):
    period: str  # YYYY-Qn
    period_end_date: date | None = None
    fields: dict[str, str]
    # Full source-label payload (in source units). Sent through to
    # `bulk-upsert` so it can be archived in `financial_imports`.
    raw_source: dict[str, str] = Field(default_factory=dict)


class ImportPreviewResponse(BaseModel):
    parser_id: str
    source: str
    statement: str
    caption: str | None = None
    rows: list[ImportRowPreview]
    unmapped_labels: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class BulkUpsertRow(QuarterlyFinancialUpsert):
    """One quarter to commit. Same shape as the per-cell upsert + the period.

    Optionally carries `raw_source` — the full source-label payload —
    which gets stored verbatim in `financial_imports` when accompanied
    by an `import_context` on the request.
    """

    period: str = Field(pattern=r"^\d{4}-Q[1-4]$")
    raw_source: dict[str, str] | None = None


class ImportContext(BaseModel):
    """Provenance of an import-driven bulk upsert. Present → write to
    `financial_imports`; absent → write only `quarterly_financials`
    (the manual-cell-edit path goes through a different endpoint, but
    callers that piggy-back on bulk-upsert manually can omit this)."""

    parser_id: str
    source: str
    statement: str
    caption: str | None = None


class BulkUpsertRequest(BaseModel):
    rows: list[BulkUpsertRow]
    import_context: ImportContext | None = None


class BulkUpsertResponse(BaseModel):
    written: int
    periods: list[str]
    raw_payloads_archived: int = 0
