"""Common types for the financial-statement importers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


# The statement types we know how to import. The first three mirror the
# data-entry tabs in the UI; "all" is for multi-statement sources (e.g.
# SEC EDGAR) whose single payload populates every tab at once.
STATEMENT_TYPES = ("income", "balance", "cashflow", "all")


@dataclass(slots=True)
class ImportedRow:
    """One quarter's worth of values for the fields the parser recognised."""

    period: str  # "YYYY-Qn"
    period_end_date: date | None
    # Map of FinancialField name -> string value (in the schema's storage
    # convention, i.e. absolute USD for monetary fields). Kept as strings
    # so source precision survives the trip into the JSON response.
    fields: dict[str, str] = field(default_factory=dict)
    # Map of source label -> source value (in the source's own units).
    # Includes labels we don't have a FinancialField column for, so future
    # features can read back the full payload.
    raw_source: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class ImportPreview:
    """What the importer hands back to the UI for review before commit."""

    parser_id: str
    source: str
    statement: str  # one of STATEMENT_TYPES
    caption: str | None
    rows: list[ImportedRow]
    unmapped_labels: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
