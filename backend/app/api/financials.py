"""Quarterly financials router — bulk read + per-quarter upsert (auto-save target)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api._helpers import get_stock_or_404
from app.db.models import FinancialImport, QuarterlyFinancial
from app.db.session import get_db
from app.schemas.financial_import import (
    BulkUpsertRequest,
    BulkUpsertResponse,
    ImportPreviewResponse,
    ImportRowPreview,
)
from app.schemas.quarterly_financial import (
    QuarterlyFinancialRead,
    QuarterlyFinancialUpsert,
)
from app.services.derivation import apply_derivations
from app.services.imports import get_parser
from app.services.providers import SecLookupError, sec_provider

# Reject files this large at the gateway — typical statement HTML is well
# under a megabyte; anything larger is almost certainly a misuse.
MAX_HTML_BYTES = 5 * 1024 * 1024

router = APIRouter(prefix="/stocks/{symbol}/financials", tags=["financials"])

PERIOD_PATTERN = r"^\d{4}-Q[1-4]$"
PeriodPath = Annotated[str, Path(pattern=PERIOD_PATTERN, examples=["2024-Q3"])]


@router.get("", response_model=list[QuarterlyFinancialRead])
def list_financials(symbol: str, db: Session = Depends(get_db)) -> list[QuarterlyFinancial]:
    stock = get_stock_or_404(db, symbol)
    return list(
        db.scalars(
            select(QuarterlyFinancial)
            .where(QuarterlyFinancial.stock_id == stock.id)
            .order_by(QuarterlyFinancial.period)
        )
    )


@router.delete("/{period}", status_code=status.HTTP_204_NO_CONTENT)
def delete_financial(
    symbol: str, period: PeriodPath, db: Session = Depends(get_db)
) -> None:
    """Hard-delete a single quarter. 404 if the row doesn't exist — the UI
    treats that case as 'nothing to delete' and just hides the column."""
    stock = get_stock_or_404(db, symbol)
    row = db.scalar(
        select(QuarterlyFinancial).where(
            QuarterlyFinancial.stock_id == stock.id,
            QuarterlyFinancial.period == period,
        )
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No financial row for {symbol} {period}.",
        )
    db.delete(row)
    db.commit()


@router.put("/{period}", response_model=QuarterlyFinancialRead)
def upsert_financial(
    symbol: str,
    period: PeriodPath,
    payload: QuarterlyFinancialUpsert,
    db: Session = Depends(get_db),
) -> QuarterlyFinancial:
    stock = get_stock_or_404(db, symbol)
    row = db.scalar(
        select(QuarterlyFinancial).where(
            QuarterlyFinancial.stock_id == stock.id,
            QuarterlyFinancial.period == period,
        )
    )
    if row is None:
        row = QuarterlyFinancial(stock_id=stock.id, period=period)
        db.add(row)

    # Only the fields the client sent are applied — absent keys preserve
    # whatever was there before, which is what auto-save-on-edit needs.
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)

    apply_derivations(row, stock_shares_outstanding=stock.shares_outstanding)

    row.updated_at = datetime.now().astimezone()
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# HTML import — preview + bulk upsert
# ---------------------------------------------------------------------------


@router.post("/import-preview", response_model=ImportPreviewResponse)
async def import_preview(
    symbol: str,
    parser_id: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    db: Session = Depends(get_db),
) -> ImportPreviewResponse:
    """Stateless: parse the uploaded HTML using the named parser and return a
    preview. The 404 on unknown stock fires here so the user gets a clear
    error before they bother filling out the dialog."""
    get_stock_or_404(db, symbol)

    parser_spec = get_parser(parser_id)
    if parser_spec is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown parser_id '{parser_id}'.",
        )

    raw = await file.read()
    if len(raw) > MAX_HTML_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"HTML file exceeds {MAX_HTML_BYTES // (1024 * 1024)} MB limit.",
        )
    try:
        text = raw.decode("utf-8", errors="replace")
        preview = parser_spec.parse(text)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    return ImportPreviewResponse(
        parser_id=preview.parser_id,
        source=preview.source,
        statement=preview.statement,
        caption=preview.caption,
        rows=[
            ImportRowPreview(
                period=row.period,
                period_end_date=row.period_end_date,
                fields=row.fields,
                raw_source=row.raw_source,
            )
            for row in preview.rows
        ],
        unmapped_labels=preview.unmapped_labels,
        warnings=preview.warnings,
    )


@router.post("/import-preview-edgar", response_model=ImportPreviewResponse)
def import_preview_edgar(
    symbol: str, db: Session = Depends(get_db)
) -> ImportPreviewResponse:
    """Fetch the stock's full XBRL companyfacts payload from SEC EDGAR
    and run it through the all-statements parser. Returns the same
    preview shape as the file-upload `import-preview` endpoint, so the
    UI's preview + bulk-save flow works unchanged."""
    stock = get_stock_or_404(db, symbol)

    if not stock.cik:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{stock.symbol} has no CIK on file. "
                "Use the Fetch CIK button in Edit Metadata first."
            ),
        )

    parser_spec = get_parser("sec_edgar_all")
    if parser_spec is None:
        # Defensive — the registry is static, so this only fires if the
        # parser module was removed without updating the registry.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="EDGAR parser is not registered on the server.",
        )

    try:
        raw_json = sec_provider.fetch_company_facts(stock.cik)
    except SecLookupError as err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(err),
        ) from err

    try:
        preview = parser_spec.parse(raw_json)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    return ImportPreviewResponse(
        parser_id=preview.parser_id,
        source=preview.source,
        statement=preview.statement,
        caption=preview.caption,
        rows=[
            ImportRowPreview(
                period=row.period,
                period_end_date=row.period_end_date,
                fields=row.fields,
                raw_source=row.raw_source,
            )
            for row in preview.rows
        ],
        unmapped_labels=preview.unmapped_labels,
        warnings=preview.warnings,
    )


@router.post("/bulk-upsert", response_model=BulkUpsertResponse)
def bulk_upsert(
    symbol: str, payload: BulkUpsertRequest, db: Session = Depends(get_db)
) -> BulkUpsertResponse:
    """Commit each row through the same upsert path as the per-cell PUT
    (derivations and partial-update semantics behave identically). When
    `import_context` accompanies the request, each row's `raw_source`
    payload is also archived in `financial_imports`."""
    stock = get_stock_or_404(db, symbol)
    ctx = payload.import_context

    written: list[str] = []
    archived = 0
    now = datetime.now().astimezone()

    # Session autoflush is off, so a `SELECT` issued in iteration N+1 won't
    # see a row added in iteration N until the explicit commit. We cache
    # what we've already touched in-request and reuse it — without this,
    # any duplicate period in `payload.rows` would `INSERT` twice and trip
    # the `(stock, period)` and `(stock, source, statement, period)`
    # unique constraints at commit time.
    qf_cache: dict[str, QuarterlyFinancial] = {}
    fi_cache: dict[str, FinancialImport] = {}

    for entry in payload.rows:
        row_data = entry.model_dump(exclude_unset=True)
        period = row_data.pop("period")
        raw_source = row_data.pop("raw_source", None)
        period_end_date = row_data.get("period_end_date")

        row = qf_cache.get(period)
        if row is None:
            row = db.scalar(
                select(QuarterlyFinancial).where(
                    QuarterlyFinancial.stock_id == stock.id,
                    QuarterlyFinancial.period == period,
                )
            )
            if row is None:
                row = QuarterlyFinancial(stock_id=stock.id, period=period)
                db.add(row)
            qf_cache[period] = row

        for field, value in row_data.items():
            setattr(row, field, value)

        apply_derivations(row, stock_shares_outstanding=stock.shares_outstanding)
        row.updated_at = now
        if period not in written:
            written.append(period)

        # Archive the raw payload only when the caller identifies the
        # import (parser/source/statement). Manual upserts skip this.
        if ctx is not None and raw_source:
            existing = fi_cache.get(period)
            if existing is None:
                existing = db.scalar(
                    select(FinancialImport).where(
                        FinancialImport.stock_id == stock.id,
                        FinancialImport.source == ctx.source,
                        FinancialImport.statement == ctx.statement,
                        FinancialImport.period == period,
                    )
                )
                if existing is None:
                    existing = FinancialImport(
                        stock_id=stock.id,
                        source=ctx.source,
                        statement=ctx.statement,
                        period=period,
                    )
                    db.add(existing)
                fi_cache[period] = existing
            existing.parser_id = ctx.parser_id
            existing.period_end_date = period_end_date
            existing.raw_payload = raw_source
            existing.source_caption = ctx.caption
            existing.imported_at = now
            archived += 1

    db.commit()
    return BulkUpsertResponse(
        written=len(written), periods=written, raw_payloads_archived=archived
    )
