"""SEC EDGAR — all-statements parser (live XBRL companyfacts).

EDGAR ships one big JSON payload per filer covering every fact across
income, balance, and cash-flow statements, so a single fetch populates
all three tabs in the data-entry grid. The parsing is involved because
we have to:

  * Pick the right XBRL concept name per logical field (multiple aliases
    per metric — companies switch tags over time).
  * Filter the per-concept entries down to one value per (period_end,
    metric) pair, preferring the most-recently-filed restatement.
  * Distinguish *flow* facts (income / cash-flow line items, have
    start+end dates and live in monthly buckets) from *instant* facts
    (balance-sheet line items, have only `end`).
  * Synthesise Q4 from `FY = Q1 + Q2 + Q3 + Q4` whenever the issuer only
    files an annual 10-K for the fourth quarter — without this step
    every fiscal year would be missing one bucket.

Storage convention: absolute USD, one ``ImportedRow`` per calendar
quarter (mapped via the midpoint rule the rest of the app uses). Source units are passed through verbatim into
``raw_source`` so the archive in `financial_imports` can carry concepts
we don't yet have a schema column for.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from app.services.imports._numeric import _format_decimal, _quarter_for
from app.services.imports.types import ImportedRow, ImportPreview

PARSER_ID = "sec_edgar_all"
SOURCE = "sec_edgar"
STATEMENT = "all"
LABEL = "SEC EDGAR — All Statements (live, XBRL companyfacts)"

DEFAULT_CAPTION = (
    "Stored in absolute US$ (SEC EDGAR XBRL companyfacts; "
    "Q4 derived from 10-K when only annual is filed)"
)

# Period (flow) facts: live in (start, end) windows. The parser scales by
# 1 (EDGAR ships absolute USD already). The XBRL units to accept per
# concept are listed alongside the candidate concept names — most are
# `USD`, EPS uses `USD/shares`, share counts use `shares`.
#
# The third tuple element flags whether the metric is *additive*:
#   True  → fiscal-year value equals the sum of its four quarters.
#           Enables Q4 = FY − (Q1+Q2+Q3) synthesis when the issuer
#           only files 10-K for the fourth quarter. EPS is treated as
#           additive because, with stable share counts, annual EPS is
#           approximately the sum of quarterly EPS.
#   False → fiscal-year value is an *average* of the four quarters
#           rather than a sum (weighted-average shares outstanding).
#           Subtracting would produce nonsense (e.g. negative billions
#           of shares); instead we use the annual figure directly at
#           the FY end-date as the Q4 approximation, since the annual
#           weighted average ≈ Q4 share count to within a per-cent.
_FLOW_FIELDS: dict[str, tuple[list[str], tuple[str, ...], bool]] = {
    "revenue": (
        [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
            "SalesRevenueGoodsNet",
        ],
        ("USD",),
        True,
    ),
    "cogs": (
        [
            "CostOfGoodsAndServicesSold",
            "CostOfRevenue",
            "CostOfGoodsSold",
        ],
        ("USD",),
        True,
    ),
    "gross_profit": (["GrossProfit"], ("USD",), True),
    "operating_expenses": (
        [
            "OperatingExpenses",
            "CostsAndExpenses",
        ],
        ("USD",),
        True,
    ),
    "operating_income": (["OperatingIncomeLoss"], ("USD",), True),
    "interest_expense": (
        [
            "InterestExpense",
            "InterestExpenseDebt",
        ],
        ("USD",),
        True,
    ),
    "pretax_income": (
        [
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
            "IncomeLossBeforeIncomeTaxes",
        ],
        ("USD",),
        True,
    ),
    "net_income": (["NetIncomeLoss"], ("USD",), True),
    "ebitda": (
        [
            "EarningsBeforeInterestTaxesDepreciationAndAmortization",
        ],
        ("USD",),
        True,
    ),
    "eps_basic": (["EarningsPerShareBasic"], ("USD/shares",), True),
    "eps_diluted": (["EarningsPerShareDiluted"], ("USD/shares",), True),
    "shares_outstanding_diluted": (
        [
            "WeightedAverageNumberOfDilutedSharesOutstanding",
            "WeightedAverageNumberOfSharesOutstandingBasic",
        ],
        ("shares",),
        False,
    ),
    "operating_cash_flow": (
        ["NetCashProvidedByUsedInOperatingActivities"],
        ("USD",),
        True,
    ),
    "capex": (
        [
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "PaymentsToAcquireProductiveAssets",
        ],
        ("USD",),
        True,
    ),
    "dividends_paid": (
        [
            "PaymentsOfDividends",
            "PaymentsOfDividendsCommonStock",
        ],
        ("USD",),
        True,
    ),
    "stock_buybacks": (
        ["PaymentsForRepurchaseOfCommonStock"],
        ("USD",),
        True,
    ),
}

# Instant (balance-sheet) facts: single `end` date per entry.
_INSTANT_FIELDS: dict[str, tuple[list[str], tuple[str, ...]]] = {
    "cash_and_equivalents": (
        [
            "CashAndCashEquivalentsAtCarryingValue",
            "Cash",
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        ],
        ("USD",),
    ),
    "short_term_investments": (
        [
            # Apple switched from `AvailableForSaleSecuritiesCurrent`
            # to `MarketableSecuritiesCurrent` at Sep 29 2018 (the FY19
            # cutover). Both tags overlap at the boundary; listing the
            # newer one first means current quarters resolve directly,
            # older ones fall back without manual intervention.
            "MarketableSecuritiesCurrent",
            "AvailableForSaleSecuritiesCurrent",
            "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
            "ShortTermInvestments",
        ],
        ("USD",),
    ),
    "receivables": (
        [
            "AccountsReceivableNetCurrent",
            "ReceivablesNetCurrent",
        ],
        ("USD",),
    ),
    "inventory": (
        ["InventoryNet", "Inventories"],
        ("USD",),
    ),
    "total_current_assets": (
        ["AssetsCurrent"],
        ("USD",),
    ),
    "total_assets": (
        ["Assets"],
        ("USD",),
    ),
    "short_term_debt": (
        [
            "ShortTermBorrowings",
            "CommercialPaper",
            "LongTermDebtCurrent",
        ],
        ("USD",),
    ),
    "total_current_liabilities": (
        ["LiabilitiesCurrent"],
        ("USD",),
    ),
    "long_term_debt": (
        [
            "LongTermDebtNoncurrent",
            "LongTermDebt",
        ],
        ("USD",),
    ),
    "total_liabilities": (
        ["Liabilities"],
        ("USD",),
    ),
    "total_equity": (
        [
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        ],
        ("USD",),
    ),
}


def parse(raw: str) -> ImportPreview:
    """Parse a companyfacts JSON payload into a multi-statement preview."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Not valid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError("Expected an object at the top level of companyfacts.")

    facts = _flatten_facts(data.get("facts"))
    if not facts:
        raise ValueError("companyfacts payload has no `facts` object.")

    warnings: list[str] = []

    # Per-field: {period_end_date: value-string-in-source-units}.
    field_values: dict[str, dict[date, str]] = {}
    # Per-concept-name: same shape, kept verbatim for the raw archive.
    raw_per_concept: dict[str, dict[date, str]] = {}

    for field, (concepts, units, additive) in _FLOW_FIELDS.items():
        quarterly, annual, concept_name = _resolve_flow_concept(
            facts, concepts, units, additive=additive
        )
        if quarterly is None and annual is None:
            continue
        merged = _merge_quarterly_with_annual_q4(
            quarterly or {}, annual or {}, additive=additive
        )
        if not merged:
            continue
        field_values[field] = merged
        # Archive the *same* values we just put into the field so the
        # `raw_source` payload in `financial_imports` matches what the
        # user sees in the grid. (Earlier versions archived annual-
        # overrides-quarterly which produced rows where raw_source and
        # the field column disagreed at every fiscal-year boundary —
        # and at every non-FY date where EDGAR also ships a TTM window.)
        if concept_name and concept_name not in raw_per_concept:
            raw_per_concept[concept_name] = dict(merged)

    for field, (concepts, units) in _INSTANT_FIELDS.items():
        per_period = _resolve_instant_concept(facts, concepts, units, raw_per_concept)
        if per_period:
            field_values[field] = per_period

    # EBITDA isn't directly filed by most issuers — it's a non-GAAP
    # metric — so derive it from `OperatingIncomeLoss + Depreciation &
    # Amortization`. If the issuer did file the (rarely used)
    # `EarningsBeforeInterestTaxesDepreciationAndAmortization` concept,
    # that value has already been picked up above and we leave it alone.
    if "ebitda" not in field_values:
        ebitda = _derive_ebitda(facts, field_values, raw_per_concept)
        if ebitda:
            field_values["ebitda"] = ebitda

    # Pivot: build one row per period-end across all collected metrics.
    all_period_ends: set[date] = set()
    for per_period in field_values.values():
        all_period_ends.update(per_period.keys())
    for per_period in raw_per_concept.values():
        all_period_ends.update(per_period.keys())

    # Group period-ends by calendar quarter. When several end-dates fall
    # into the same quarter (common around fiscal-year boundaries — e.g.
    # Mar 31 and Apr 30 both map to Q1 under the midpoint rule), we keep
    # the row at the LATEST end-date but merge field values across all
    # end-dates in that quarter, with later end-dates winning per-field.
    # Without this dedupe the bulk-upsert tries to INSERT two
    # `financial_imports` rows with the same `(stock, source, statement,
    # period)` scope and trips the unique constraint.
    by_quarter: dict[str, list[date]] = {}
    for period_end in sorted(all_period_ends):
        quarter = _quarter_for(period_end)
        by_quarter.setdefault(quarter, []).append(period_end)

    rows: list[ImportedRow] = []
    for quarter, ends in by_quarter.items():
        if len(ends) > 1:
            others = ", ".join(d.isoformat() for d in ends[:-1])
            warnings.append(
                f"Multiple period-ends collapsed into {quarter}: kept "
                f"{ends[-1].isoformat()}, merged from {others}."
            )

        fields: dict[str, str] = {}
        raw_source: dict[str, str] = {}
        for period_end in ends:  # already sorted oldest→newest
            for field, per_period in field_values.items():
                value = per_period.get(period_end)
                if value is not None:
                    fields[field] = value
            for concept, per_period in raw_per_concept.items():
                value = per_period.get(period_end)
                if value is not None:
                    raw_source[concept] = value

        if not fields and not raw_source:
            continue

        rows.append(
            ImportedRow(
                period=quarter,
                period_end_date=ends[-1],
                fields=fields,
                raw_source=raw_source,
            )
        )

    rows.sort(key=lambda r: r.period)

    return ImportPreview(
        parser_id=PARSER_ID,
        source=SOURCE,
        statement=STATEMENT,
        caption=DEFAULT_CAPTION,
        rows=rows,
        unmapped_labels=[],
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _flatten_facts(raw_facts: Any) -> dict[str, dict[str, Any]]:
    """Merge the `us-gaap` and `dei` namespaces into one concept dict.

    EDGAR scopes its concepts by taxonomy (`us-gaap`, `dei`, sometimes
    industry-specific ones). For our purposes every concept name we look
    up is unique across namespaces, so flattening is safe.
    """
    if not isinstance(raw_facts, dict):
        return {}
    flat: dict[str, dict[str, Any]] = {}
    for namespace in ("us-gaap", "dei", "ifrs-full"):
        ns = raw_facts.get(namespace)
        if isinstance(ns, dict):
            for concept_name, concept_payload in ns.items():
                if isinstance(concept_payload, dict) and concept_name not in flat:
                    flat[concept_name] = concept_payload
    return flat


def _resolve_flow_concept(
    facts: dict[str, dict[str, Any]],
    concept_candidates: list[str],
    accepted_units: tuple[str, ...],
    *,
    additive: bool = True,
) -> tuple[dict[date, str] | None, dict[date, str] | None, str | None]:
    """Merge per-period values across every candidate concept. Earlier
    candidates win at conflict, later candidates fill gaps — this is how
    taxonomy switches get bridged into one continuous series. The
    canonical example is Apple's Sep-2018 marketable-securities tag
    flip from ``AvailableForSaleSecuritiesCurrent`` to
    ``MarketableSecuritiesCurrent``; the older tag has FY09–FY18 data,
    the newer one FY19+, and returning only the first match would
    blank out half the history.

    Returns ``(quarterly, annual, primary_concept_name)`` — the primary
    is the first candidate that supplied any data, used as the archive
    key in ``raw_per_concept``.
    """
    quarterly_merged: dict[date, str] = {}
    annual_merged: dict[date, str] = {}
    primary_concept: str | None = None
    for concept in concept_candidates:
        payload = facts.get(concept)
        if payload is None:
            continue
        entries = _entries_for_units(payload, accepted_units)
        if not entries:
            continue
        quarterly, annual = _bucket_flow_entries(entries, additive=additive)
        if not quarterly and not annual:
            continue
        for end, val in quarterly.items():
            quarterly_merged.setdefault(end, val)
        for end, val in annual.items():
            annual_merged.setdefault(end, val)
        if primary_concept is None:
            primary_concept = concept
    if not quarterly_merged and not annual_merged:
        return None, None, None
    return quarterly_merged, annual_merged, primary_concept


def _resolve_instant_concept(
    facts: dict[str, dict[str, Any]],
    concept_candidates: list[str],
    accepted_units: tuple[str, ...],
    raw_per_concept: dict[str, dict[date, str]],
) -> dict[date, str]:
    """Merge per-period values across every candidate concept (same
    tag-switching rationale as ``_resolve_flow_concept``). Primary
    candidate wins at conflict; fallbacks fill in gaps."""
    merged: dict[date, str] = {}
    primary_concept: str | None = None
    for concept in concept_candidates:
        payload = facts.get(concept)
        if payload is None:
            continue
        entries = _entries_for_units(payload, accepted_units)
        if not entries:
            continue
        per_period = _bucket_instant_entries(entries)
        if not per_period:
            continue
        for end, val in per_period.items():
            merged.setdefault(end, val)
        if primary_concept is None:
            primary_concept = concept
    if merged and primary_concept and primary_concept not in raw_per_concept:
        raw_per_concept[primary_concept] = dict(merged)
    return merged


def _entries_for_units(
    payload: dict[str, Any], accepted_units: tuple[str, ...]
) -> list[dict[str, Any]]:
    units = payload.get("units")
    if not isinstance(units, dict):
        return []
    for u in accepted_units:
        bucket = units.get(u)
        if isinstance(bucket, list) and bucket:
            return bucket
    return []


def _bucket_flow_entries(
    entries: list[dict[str, Any]],
    *,
    additive: bool = True,
) -> tuple[dict[date, str], dict[date, str]]:
    """Group flow entries into per-quarter and per-annual maps.

    Three flavors of XBRL flow reporting are handled in one pass:

      1. **Direct 3-month entries** — income-statement-style, where the
         filer ships a standalone (start, end) window covering one
         quarter. Captured by duration filter.
      2. **Cumulative YTD chains** — cash-flow-statement-style, where
         the filer ships 3 / 6 / 9 / 12-month windows all sharing the
         same fiscal-year *start* and increasing ends. Standalone
         quarterly values are derived by subtracting consecutive YTD
         values (`standalone_Q2 = H1_YTD − Q1`, etc.).
      3. **Annual 12-month entries** — collected separately so the
         FY-end synthesis fallback in ``_merge_quarterly_with_annual_q4``
         still has something to use when neither direct nor YTD-chain
         data is available.

    Direct 3-month entries are preferred over YTD-derived values for
    the same end-date (they're filed-as-is rather than computed). YTD
    chain derivation is only done when ``additive=True`` — for
    weighted-average fields (shares outstanding), differencing two YTD
    averages does not yield a sensible standalone quarter.

    Restatements are absorbed by keeping the most-recently-filed value
    per (start, end) pair.
    """
    # Step 1: index by (start, end) with latest-filed-wins.
    by_se: dict[tuple[date, date], Decimal] = {}
    by_se_filed: dict[tuple[date, date], str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        form = entry.get("form", "")
        if not isinstance(form, str) or not form.startswith(("10-K", "10-Q")):
            continue
        start = _parse_date(entry.get("start"))
        end = _parse_date(entry.get("end"))
        if start is None or end is None:
            continue
        val_str = _value_str(entry.get("val"))
        if val_str is None:
            continue
        try:
            val = Decimal(val_str)
        except InvalidOperation:
            continue
        key = (start, end)
        filed = entry.get("filed") if isinstance(entry.get("filed"), str) else ""
        if filed > by_se_filed.get(key, ""):
            by_se[key] = val
            by_se_filed[key] = filed

    # Step 2: direct 3-month and 12-month picks.
    direct_quarterly: dict[date, Decimal] = {}
    annual: dict[date, Decimal] = {}
    for (start, end), val in by_se.items():
        duration = (end - start).days + 1
        if 80 <= duration <= 100:
            direct_quarterly[end] = val
        elif 350 <= duration <= 380:
            annual[end] = val

    # Step 3: YTD-chain derivation (additive metrics only).
    derived_quarterly: dict[date, Decimal] = {}
    if additive:
        by_start: dict[date, list[tuple[date, Decimal]]] = {}
        for (start, end), val in by_se.items():
            by_start.setdefault(start, []).append((end, val))
        for start, end_vals in by_start.items():
            end_vals.sort(key=lambda x: x[0])
            # Phantom prior endpoint = day before chain start; first segment's
            # delta then equals the first YTD value itself.
            prev_end = start - timedelta(days=1)
            prev_val = Decimal(0)
            for end, val in end_vals:
                segment_days = (end - prev_end).days
                if 80 <= segment_days <= 100 and end not in direct_quarterly:
                    derived_quarterly[end] = val - prev_val
                prev_end = end
                prev_val = val

    # Direct wins over derived when both exist.
    quarterly_out: dict[date, str] = {
        end: _format_decimal(val) for end, val in derived_quarterly.items()
    }
    for end, val in direct_quarterly.items():
        quarterly_out[end] = _format_decimal(val)

    return quarterly_out, {d: _format_decimal(v) for d, v in annual.items()}


def _bucket_instant_entries(entries: list[dict[str, Any]]) -> dict[date, str]:
    by_end: dict[date, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        form = entry.get("form", "")
        if not isinstance(form, str) or not form.startswith(("10-K", "10-Q")):
            continue
        end = _parse_date(entry.get("end"))
        if end is None:
            continue
        existing = by_end.get(end)
        if existing is None or _filed_after(entry, existing):
            by_end[end] = entry
    return {d: v for d, e in by_end.items() if (v := _value_str(e.get("val"))) is not None}


def _merge_quarterly_with_annual_q4(
    quarterly: dict[date, str],
    annual: dict[date, str],
    *,
    additive: bool = True,
) -> dict[date, str]:
    """Return the quarterly map augmented with derived Q4 values.

    For ``additive=True`` (true flow values — revenue, net income, cash
    flows, and EPS): for each annual entry's end-date E_a, find three
    quarterly entries whose end-dates fall in (E_a − 365, E_a). If
    exactly three are found, compute Q4 = FY − sum and insert at E_a.
    If fewer than three quarters exist, fall back to storing the annual
    value at E_a so the user gets *some* coverage for that fiscal year.

    For ``additive=False`` (averaged values — weighted-average shares):
    annual ≈ Q4 directly (the annual weighted-average is within a
    per-cent of the year-end share count for typical filers, since
    buybacks/issuances move it only gradually). We use the annual
    figure as-is at E_a, with no subtraction.

    If the annual end-date itself already has a quarterly value, the
    quarterly value is kept untouched in both modes.
    """
    merged: dict[date, str] = dict(quarterly)
    if not annual:
        return merged

    quarter_ends_sorted = sorted(quarterly.keys())

    for fy_end, fy_value_str in annual.items():
        if fy_end in merged:
            continue  # Already covered by a real 10-Q-equivalent entry.
        if not additive:
            # Averaged metric: annual ≈ Q4, use directly.
            merged[fy_end] = fy_value_str
            continue
        window_start = fy_end - timedelta(days=365)
        candidates = [d for d in quarter_ends_sorted if window_start < d < fy_end]
        if len(candidates) < 3:
            # Not enough quarterly data to derive Q4 — fall back to the
            # annual value at the FY end-date so the user at least gets
            # *some* coverage for that year.
            merged[fy_end] = fy_value_str
            continue
        # Take the three closest quarters before the FY end.
        last_three = candidates[-3:]
        try:
            fy_val = Decimal(fy_value_str)
            q_sum = sum(Decimal(merged[d]) for d in last_three)
            q4 = fy_val - q_sum
        except (InvalidOperation, KeyError):
            continue
        merged[fy_end] = _format_decimal(q4)
    return merged


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _value_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            return _format_decimal(Decimal(str(value)))
        except InvalidOperation:
            return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return None


# A genuine single-line D&A concept, when the issuer files one (e.g. Apple's
# `DepreciationDepletionAndAmortization`). Preferred over summing components.
_DA_COMBINED_CONCEPTS = [
    "DepreciationDepletionAndAmortization",
    "DepreciationAndAmortization",
    "DepreciationAmortizationAndAccretionNet",
    "DepreciationAmortizationAndOther",
]

# When no combined tag exists, D&A is summed from these components. Depreciation
# is the anchor — amortization pieces are added only at period-ends where it
# reports — so we never assemble a partial (understated) D&A figure.
_DA_AMORTIZATION_COMPONENTS = [
    "AmortizationOfIntangibleAssets",
    "CapitalizedComputerSoftwareAmortization",
    "CapitalizedComputerSoftwareAmortization1",
    "FinanceLeaseRightOfUseAssetAmortization",
]


def _combine_anchored_on_depreciation(
    anchor: dict[date, str], components: list[dict[date, str]]
) -> dict[date, str]:
    """Sum `Depreciation` with each amortization component present at the same
    period-end. Anchored on depreciation so we never build a partial D&A."""
    out: dict[date, str] = {}
    for period_end, dep_value in anchor.items():
        try:
            total = Decimal(dep_value)
        except (InvalidOperation, ArithmeticError):
            continue
        for comp in components:
            if period_end in comp:
                try:
                    total += Decimal(comp[period_end])
                except (InvalidOperation, ArithmeticError):
                    continue
        out[period_end] = _format_decimal(total)
    return out


def _sum_da_components(
    facts: dict[str, dict[str, Any]],
) -> tuple[dict[date, str], dict[date, str]]:
    """D&A summed from its components, anchored on `Depreciation`.

    Many issuers (e.g. Microsoft) don't file a combined D&A line — they report
    depreciation and the amortization pieces under separate tags. We anchor on
    `Depreciation` and add each amortization component that also reports a value
    for the same period-end. Returns ``(quarterly, annual)`` maps.
    """
    dep_quarterly, dep_annual, _ = _resolve_flow_concept(
        facts, ["Depreciation"], ("USD",), additive=True
    )
    if not dep_quarterly and not dep_annual:
        return {}, {}

    comp_quarterly_maps: list[dict[date, str]] = []
    comp_annual_maps: list[dict[date, str]] = []
    for concept in _DA_AMORTIZATION_COMPONENTS:
        comp_q, comp_a, _ = _resolve_flow_concept(
            facts, [concept], ("USD",), additive=True
        )
        if comp_q:
            comp_quarterly_maps.append(comp_q)
        if comp_a:
            comp_annual_maps.append(comp_a)

    return (
        _combine_anchored_on_depreciation(dep_quarterly or {}, comp_quarterly_maps),
        _combine_anchored_on_depreciation(dep_annual or {}, comp_annual_maps),
    )


def _spread_annual_da(
    da_quarterly: dict[date, str],
    da_annual: dict[date, str],
    op_ends: list[date],
    revenue: dict[date, str],
) -> dict[date, str]:
    """Fill quarters that lack a real quarterly D&A by spreading the fiscal
    year's annual D&A across that year's quarters.

    Allocation is pro-rata by quarterly revenue (D&A/revenue is fairly stable,
    so this tracks seasonality better than an even split); falls back to an even
    split when any quarter's revenue is missing/non-positive. A fiscal year that
    already has *any* real quarterly D&A is skipped entirely, so genuine
    quarterly disclosures are never double-counted.
    """
    da = dict(da_quarterly)
    for annual_end, annual_value in da_annual.items():
        members = [e for e in op_ends if annual_end - timedelta(days=366) < e <= annual_end]
        if not members or any(e in da_quarterly for e in members):
            continue
        try:
            total_da = Decimal(annual_value)
        except (InvalidOperation, ArithmeticError):
            continue

        revs: dict[date, Decimal] = {}
        usable = True
        for e in members:
            raw = revenue.get(e)
            if raw is None:
                usable = False
                break
            try:
                rev = Decimal(raw)
            except (InvalidOperation, ArithmeticError):
                usable = False
                break
            if rev <= 0:
                usable = False
                break
            revs[e] = rev

        rev_total = sum(revs.values()) if usable else Decimal(0)
        if usable and rev_total > 0:
            for e in members:
                da.setdefault(e, _format_decimal(total_da * revs[e] / rev_total))
        else:
            share = total_da / Decimal(len(members))
            for e in members:
                da.setdefault(e, _format_decimal(share))
    return da


def _derive_ebitda(
    facts: dict[str, dict[str, Any]],
    field_values: dict[str, dict[date, str]],
    raw_per_concept: dict[str, dict[date, str]],
) -> dict[date, str]:
    """Compute EBITDA = OperatingIncome + Depreciation & Amortization per period.

    Operating Income comes from the already-populated
    ``field_values['operating_income']``. D&A is taken from a combined tag if
    the issuer files one, otherwise summed from its components
    (depreciation + intangible / software / finance-lease amortization).

    Real quarterly D&A is used wherever the issuer files it. For fiscal years
    where D&A is disclosed only annually, the annual figure is spread across the
    year's quarters (pro-rata by revenue) rather than dumped onto a single
    quarter — so every quarter gets a sensible EBITDA instead of one inflated
    bucket and three blanks. Returns ``{}`` if operating income or D&A is missing.
    """
    op_income = field_values.get("operating_income")
    if not op_income:
        return {}

    # Prefer a single combined D&A line; else sum the components.
    da_quarterly, da_annual, da_concept = _resolve_flow_concept(
        facts, _DA_COMBINED_CONCEPTS, ("USD",), additive=True
    )
    if not da_quarterly and not da_annual:
        da_quarterly, da_annual = _sum_da_components(facts)
        da_concept = "Depreciation+Amortization (summed)"
    if not da_quarterly and not da_annual:
        return {}

    da = _spread_annual_da(
        da_quarterly or {},
        da_annual or {},
        sorted(op_income.keys()),
        field_values.get("revenue") or {},
    )
    if not da:
        return {}

    if da_concept and da_concept not in raw_per_concept:
        raw_per_concept[da_concept] = dict(da)

    ebitda: dict[date, str] = {}
    for period_end in op_income.keys() & da.keys():
        try:
            value = Decimal(op_income[period_end]) + Decimal(da[period_end])
        except (InvalidOperation, ArithmeticError):
            continue
        ebitda[period_end] = _format_decimal(value)
    return ebitda


def _filed_after(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Compare two entries by their `filed` date (ISO YYYY-MM-DD), most
    recent wins. Falls back to lexicographic comparison; absent filed
    dates sort below present ones."""
    fa = a.get("filed") if isinstance(a.get("filed"), str) else ""
    fb = b.get("filed") if isinstance(b.get("filed"), str) else ""
    return fa > fb
