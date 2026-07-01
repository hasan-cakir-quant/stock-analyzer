/**
 * Quarterly data-entry grid (Task 19).
 *
 * Wraps a tabbed (Income / Balance / Cash Flow / Market) spreadsheet
 * where rows are line items and columns are quarters. Each cell auto-
 * saves 500 ms after the user stops typing. Tab/arrow keys move between
 * cells; multi-cell paste from Excel parses the TSV and saves each cell
 * immediately (no per-cell debounce on paste).
 *
 * Add / remove quarter live in the column header. Removal is local-only
 * (the backend currently has no per-quarter DELETE endpoint) — the
 * column hides from this view until refresh.
 */

import { Download, Upload, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { CollapsibleSection } from "@/components/CollapsibleSection";
import { SaveIndicator, type SaveState } from "@/components/SaveIndicator";
import {
  type FinancialField,
  type FinancialRow,
  type FinancialUpsert,
  useDeleteFinancial,
  useFetchClosingPrices,
  useFinancials,
  useUpsertFinancial,
} from "@/lib/financials";
import { useToast } from "@/stores/toast";
import { compareQuarters } from "@/lib/quarters";
import { useAbbreviatedFormat } from "@/lib/settings";
import { cn } from "@/lib/utils";

import { AddQuarterPicker } from "./AddQuarterPicker";
import { ImportHtmlDialog } from "./ImportHtmlDialog";
import { type DeriveContext, TABS, type FieldDef, type TabId } from "./fields";

interface FinancialsGridProps {
  symbol: string;
  /** Stock-level shares outstanding — used as a fallback for EPS derivation hints. */
  stockSharesOutstanding?: string | number | null;
  /** Free-text reminder of the units the user enters values in. */
  unitsNote?: string | null;
}

const SAVED_HOLD_MS = 1500;

// ---------------------------------------------------------------------------

export function FinancialsGrid({
  symbol,
  stockSharesOutstanding,
  unitsNote,
}: FinancialsGridProps) {
  const financialsQuery = useFinancials(symbol);
  const upsert = useUpsertFinancial(symbol);
  const deleteFinancial = useDeleteFinancial(symbol);
  const fetchClosingPrices = useFetchClosingPrices(symbol);
  const toast = useToast();

  const deriveContext = useMemo<DeriveContext>(
    () => ({
      stockSharesOutstanding:
        stockSharesOutstanding === null || stockSharesOutstanding === undefined
          ? null
          : Number(stockSharesOutstanding),
    }),
    [stockSharesOutstanding],
  );

  const serverRows: FinancialRow[] = useMemo(
    () => financialsQuery.data ?? [],
    [financialsQuery.data],
  );

  // Quarter list = union of server periods + locally added, minus hidden.
  const [extraPeriods, setExtraPeriods] = useState<string[]>([]);
  const [hiddenPeriods, setHiddenPeriods] = useState<string[]>([]);

  const periods = useMemo(() => {
    const set = new Set<string>();
    for (const row of serverRows) set.add(row.period);
    for (const p of extraPeriods) set.add(p);
    for (const p of hiddenPeriods) set.delete(p);
    return Array.from(set).sort(compareQuarters);
  }, [serverRows, extraPeriods, hiddenPeriods]);

  const rowsByPeriod = useMemo(() => {
    const map = new Map<string, FinancialRow>();
    for (const row of serverRows) map.set(row.period, row);
    return map;
  }, [serverRows]);

  // Per-cell save state. Keyed by `${period}::${field}`.
  const [saveStates, setSaveStates] = useState<Record<string, SaveState>>({});
  const debounceTimers = useRef<Map<string, number>>(new Map());
  const savedHoldTimers = useRef<Map<string, number>>(new Map());

  // Per-cell local edit value (null when not currently being edited).
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  // Refs for programmatic focus during keyboard nav and paste targeting.
  const inputRefs = useRef<Map<string, HTMLInputElement | null>>(new Map());

  useEffect(() => {
    return () => {
      for (const t of debounceTimers.current.values()) window.clearTimeout(t);
      for (const t of savedHoldTimers.current.values()) window.clearTimeout(t);
    };
  }, []);

  function cellKey(period: string, field: FinancialField): string {
    return `${period}::${field}`;
  }

  function setSaveState(key: string, state: SaveState) {
    setSaveStates((prev) => ({ ...prev, [key]: state }));
  }

  function clearDraft(key: string) {
    setDrafts((prev) => {
      if (!(key in prev)) return prev;
      const { [key]: _omit, ...rest } = prev;
      return rest;
    });
  }

  async function saveCell(period: string, field: FinancialField, raw: string) {
    const key = cellKey(period, field);
    const trimmed = raw.trim();
    const body: FinancialUpsert = { [field]: trimmed === "" ? null : trimmed };
    setSaveState(key, "saving");
    try {
      await upsert.mutateAsync({ period, body });
      // Server-side derivation may have populated other fields too — let
      // them surface from the refetched cache instead of the local draft.
      clearDraft(key);
      setSaveState(key, "saved");
      const existing = savedHoldTimers.current.get(key);
      if (existing) window.clearTimeout(existing);
      const timer = window.setTimeout(() => {
        setSaveState(key, "idle");
        savedHoldTimers.current.delete(key);
      }, SAVED_HOLD_MS);
      savedHoldTimers.current.set(key, timer);
    } catch {
      setSaveState(key, "error");
    }
  }

  function scheduleSave(period: string, field: FinancialField, raw: string) {
    const key = cellKey(period, field);
    const existing = debounceTimers.current.get(key);
    if (existing) window.clearTimeout(existing);
    const timer = window.setTimeout(() => {
      debounceTimers.current.delete(key);
      void saveCell(period, field, raw);
    }, 500);
    debounceTimers.current.set(key, timer);
  }

  function handleCellChange(period: string, field: FinancialField, raw: string) {
    const key = cellKey(period, field);
    setDrafts((prev) => ({ ...prev, [key]: raw }));
    scheduleSave(period, field, raw);
  }

  function handleAddQuarter(period: string) {
    if (!periods.includes(period)) {
      setExtraPeriods((prev) => [...prev, period]);
    }
    // If the user previously hid this period, un-hide it so it's visible again.
    setHiddenPeriods((prev) => prev.filter((p) => p !== period));
  }

  async function handleRemoveQuarter(period: string) {
    const onServer = rowsByPeriod.has(period);
    if (onServer) {
      const ok = window.confirm(
        `Delete ${period}? This permanently removes the row and every cell value for that quarter.`,
      );
      if (!ok) return;
      try {
        await deleteFinancial.mutateAsync(period);
        toast.show(`${period} deleted`, { tone: "success" });
      } catch {
        toast.show(`Failed to delete ${period}`, { tone: "error" });
        return;
      }
    }
    // Drop from any local view state regardless — the cache write in the
    // mutation already removed the server row.
    setHiddenPeriods((prev) => (prev.includes(period) ? prev : [...prev, period]));
    setExtraPeriods((prev) => prev.filter((p) => p !== period));
  }

  async function handleFetchClosingPrices() {
    // Periods the user can currently see — covers both server rows and
    // locally added drafts. Skips hidden ones the user removed.
    if (periods.length === 0) {
      toast.show("Add at least one quarter first.", { tone: "error" });
      return;
    }
    try {
      const response = await fetchClosingPrices.mutateAsync(periods);
      let written = 0;
      const skipped: string[] = [];
      for (const entry of response.prices) {
        if (entry.closing_price === null) {
          skipped.push(entry.period);
          continue;
        }
        const key = cellKey(entry.period, "closing_price");
        // Drop any pending debounce for this cell — we save immediately.
        const pending = debounceTimers.current.get(key);
        if (pending) {
          window.clearTimeout(pending);
          debounceTimers.current.delete(key);
        }
        setDrafts((prev) => ({ ...prev, [key]: entry.closing_price! }));
        await saveCell(entry.period, "closing_price", entry.closing_price);
        written += 1;
      }
      if (written === 0) {
        toast.show("No closing prices returned.", { tone: "error" });
      } else {
        const suffix = skipped.length ? ` (skipped ${skipped.join(", ")})` : "";
        toast.show(`Fetched ${written} closing price${written === 1 ? "" : "s"}${suffix}`, {
          tone: "success",
        });
      }
    } catch (err) {
      toast.show(
        err instanceof Error ? `Fetch failed — ${err.message}` : "Fetch failed.",
        { tone: "error" },
      );
    }
  }

  // ----- Keyboard navigation ---------------------------------------------

  function moveFocus(
    fields: FieldDef[],
    period: string,
    field: FinancialField,
    rowDelta: number,
    colDelta: number,
  ) {
    const rowIdx = fields.findIndex((f) => f.key === field);
    const colIdx = periods.indexOf(period);
    if (rowIdx === -1 || colIdx === -1) return;
    const nextRow = Math.min(Math.max(rowIdx + rowDelta, 0), fields.length - 1);
    const nextCol = Math.min(Math.max(colIdx + colDelta, 0), periods.length - 1);
    const nextField = fields[nextRow].key;
    const nextPeriod = periods[nextCol];
    const ref = inputRefs.current.get(cellKey(nextPeriod, nextField));
    if (ref) {
      ref.focus();
      ref.select();
    }
  }

  // ----- Paste -----------------------------------------------------------

  function handlePaste(
    event: React.ClipboardEvent<HTMLInputElement>,
    fields: FieldDef[],
    period: string,
    field: FinancialField,
  ) {
    const text = event.clipboardData.getData("text");
    if (!text || !/[\t\n]/.test(text)) return; // single-cell paste, let the input handle it

    event.preventDefault();
    const rows = text.replace(/\r/g, "").split("\n").map((line) => line.split("\t"));
    // Trim a trailing empty row (Excel often adds one).
    while (rows.length && rows[rows.length - 1].every((cell) => cell === "")) rows.pop();

    const startRow = fields.findIndex((f) => f.key === field);
    const startCol = periods.indexOf(period);
    if (startRow === -1 || startCol === -1) return;

    for (let r = 0; r < rows.length; r++) {
      const fieldIdx = startRow + r;
      if (fieldIdx >= fields.length) break;
      const targetField = fields[fieldIdx].key;
      const cells = rows[r];

      for (let c = 0; c < cells.length; c++) {
        const periodIdx = startCol + c;
        if (periodIdx >= periods.length) break;
        const targetPeriod = periods[periodIdx];
        const value = cells[c];

        const key = cellKey(targetPeriod, targetField);
        // Drop any pending debounce for this cell — paste saves immediately.
        const pending = debounceTimers.current.get(key);
        if (pending) {
          window.clearTimeout(pending);
          debounceTimers.current.delete(key);
        }
        setDrafts((prev) => ({ ...prev, [key]: value }));
        void saveCell(targetPeriod, targetField, value);
      }
    }
  }

  // ----- Render ----------------------------------------------------------

  const [activeTab, setActiveTab] = useState<TabId>("income");
  const [importOpen, setImportOpen] = useState(false);
  const activeTabDef = TABS.find((t) => t.id === activeTab) ?? TABS[0];
  const collapseDefault = serverRows.length >= 4;

  if (financialsQuery.isLoading) {
    return (
      <CollapsibleSection title="Data Entry">
        <p className="text-xs text-muted-foreground">Loading…</p>
      </CollapsibleSection>
    );
  }

  return (
    <>
    <CollapsibleSection title="Data Entry" defaultOpen={!collapseDefault}>
      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <TabBar active={activeTab} onChange={setActiveTab} />
          <div className="flex items-center gap-1.5">
            {activeTab === "market" && (
              <button
                type="button"
                onClick={handleFetchClosingPrices}
                disabled={fetchClosingPrices.isPending || periods.length === 0}
                title="Fetch end-of-quarter closing prices from Yahoo Finance"
                className="inline-flex items-center gap-1 rounded-md border border-border bg-secondary px-2 py-0.5 text-[11px] text-secondary-foreground hover:bg-accent disabled:opacity-50"
              >
                <Download className="h-3 w-3" />
                {fetchClosingPrices.isPending ? "Fetching…" : "Fetch closing prices"}
              </button>
            )}
            <button
              type="button"
              onClick={() => setImportOpen(true)}
              className="inline-flex items-center gap-1 rounded-md border border-border bg-secondary px-2 py-0.5 text-[11px] text-secondary-foreground hover:bg-accent"
            >
              <Upload className="h-3 w-3" />
              Import file
            </button>
            <AddQuarterPicker existingPeriods={periods} onAdd={handleAddQuarter} />
          </div>
        </div>

        {unitsNote && (
          <div
            className="rounded-md border border-warning/30 bg-warning/10 px-2 py-0.5 text-[10px] text-warning"
            title="Edit via Edit metadata to change."
          >
            <span className="font-semibold">Units:</span> {unitsNote}
          </div>
        )}

        {periods.length === 0 ? (
          <div className="rounded-md border border-dashed border-border bg-card/40 p-2 text-[11px] text-muted-foreground">
            No quarters yet — click <span className="font-medium text-foreground">Add quarter</span>.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-separate border-spacing-0 text-[11px]">
              <thead>
                <tr>
                  <th className="sticky left-0 z-10 min-w-[140px] bg-card px-2 py-1 text-left font-medium text-muted-foreground">
                    Line item
                  </th>
                  {periods.map((period) => {
                    const endDate = rowsByPeriod.get(period)?.period_end_date;
                    return (
                      <th
                        key={period}
                        className="min-w-[100px] border-l border-border px-2 py-1 text-left font-medium tabular-nums"
                      >
                        <div className="flex items-center justify-between gap-1">
                          <div className="flex flex-col leading-tight">
                            <span>{period}</span>
                            {endDate && (
                              <span
                                className="text-[9px] font-normal text-muted-foreground"
                                title={`Reporting period ended ${endDate}`}
                              >
                                ends {endDate}
                              </span>
                            )}
                          </div>
                          <button
                            type="button"
                            onClick={() => void handleRemoveQuarter(period)}
                            title={
                              rowsByPeriod.has(period)
                                ? "Delete this quarter (asks for confirmation)"
                                : "Remove this draft quarter from the grid"
                            }
                            className="rounded p-0.5 text-muted-foreground hover:bg-destructive/20 hover:text-destructive"
                          >
                            <X className="h-3 w-3" />
                          </button>
                        </div>
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {activeTabDef.fields.map((fieldDef) => (
                  <tr key={fieldDef.key} className="border-t border-border">
                    <th
                      scope="row"
                      className="sticky left-0 z-10 bg-card px-2 py-0.5 text-left text-muted-foreground"
                    >
                      {fieldDef.label}
                    </th>
                    {periods.map((period) => (
                      <Cell
                        key={period}
                        period={period}
                        fieldDef={fieldDef}
                        row={rowsByPeriod.get(period)}
                        deriveContext={deriveContext}
                        draft={drafts[cellKey(period, fieldDef.key)]}
                        saveState={saveStates[cellKey(period, fieldDef.key)] ?? "idle"}
                        onChange={(value) => handleCellChange(period, fieldDef.key, value)}
                        onKeyDown={(event) => {
                          if (event.key === "ArrowDown") {
                            event.preventDefault();
                            moveFocus(activeTabDef.fields, period, fieldDef.key, 1, 0);
                          } else if (event.key === "ArrowUp") {
                            event.preventDefault();
                            moveFocus(activeTabDef.fields, period, fieldDef.key, -1, 0);
                          } else if (event.key === "ArrowRight" || (event.key === "Tab" && !event.shiftKey)) {
                            event.preventDefault();
                            moveFocus(activeTabDef.fields, period, fieldDef.key, 0, 1);
                          } else if (event.key === "ArrowLeft" || (event.key === "Tab" && event.shiftKey)) {
                            event.preventDefault();
                            moveFocus(activeTabDef.fields, period, fieldDef.key, 0, -1);
                          } else if (event.key === "Enter") {
                            event.preventDefault();
                            moveFocus(activeTabDef.fields, period, fieldDef.key, 1, 0);
                          }
                        }}
                        onPaste={(event) =>
                          handlePaste(event, activeTabDef.fields, period, fieldDef.key)
                        }
                        registerRef={(el) => {
                          const key = cellKey(period, fieldDef.key);
                          if (el) inputRefs.current.set(key, el);
                          else inputRefs.current.delete(key);
                        }}
                      />
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </CollapsibleSection>
    <ImportHtmlDialog
      symbol={symbol}
      open={importOpen}
      onClose={() => setImportOpen(false)}
    />
    </>
  );
}

// ---------------------------------------------------------------------------

function TabBar({
  active,
  onChange,
}: {
  active: TabId;
  onChange: (id: TabId) => void;
}) {
  return (
    <div className="flex items-center gap-0.5 rounded-md border border-border bg-card p-0.5">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          type="button"
          onClick={() => onChange(tab.id)}
          className={cn(
            "rounded px-2 py-0.5 text-[11px]",
            active === tab.id
              ? "bg-secondary text-secondary-foreground"
              : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------

interface CellProps {
  period: string;
  fieldDef: FieldDef;
  row: FinancialRow | undefined;
  deriveContext: DeriveContext;
  draft: string | undefined;
  saveState: SaveState;
  onChange: (value: string) => void;
  onKeyDown: (event: React.KeyboardEvent<HTMLInputElement>) => void;
  onPaste: (event: React.ClipboardEvent<HTMLInputElement>) => void;
  registerRef: (el: HTMLInputElement | null) => void;
}

function Cell({
  period,
  fieldDef,
  row,
  deriveContext,
  draft,
  saveState,
  onChange,
  onKeyDown,
  onPaste,
  registerRef,
}: CellProps) {
  const stored = row ? row[fieldDef.key] : null;
  const rawValue = draft ?? (stored === null || stored === undefined ? "" : stored);
  const formatAbbreviated = useAbbreviatedFormat();

  // Display the abbreviated magnitude (e.g. "1.32B") when the cell is not
  // being edited so the absolute-USD storage stays readable. Focus swaps
  // back to the raw editable string. `formatAbbreviated` no-ops for
  // values < 1,000 (so EPS-style figures still appear as "0.10").
  const [isFocused, setIsFocused] = useState(false);
  const numericValue = rawValue === "" ? null : Number(rawValue);
  const displayValue =
    isFocused || rawValue === "" || numericValue === null || !Number.isFinite(numericValue)
      ? rawValue
      : formatAbbreviated(numericValue);

  // Compute a "would-be derived" value when the field has no stored value
  // but its inputs are present. Shown as a hint until the user overrides.
  const derivedHint =
    fieldDef.derive && row && stored === null
      ? fieldDef.derive(row, deriveContext)
      : null;

  const looksDerived =
    fieldDef.derive &&
    row &&
    stored !== null &&
    derivedMatchesStored(fieldDef, row, stored, deriveContext);

  return (
    <td className="border-l border-t border-border align-middle">
      <div className="relative flex items-center">
        <input
          ref={registerRef}
          data-period={period}
          data-field={fieldDef.key}
          value={displayValue}
          onChange={(event) => onChange(event.target.value)}
          onFocus={(event) => {
            setIsFocused(true);
            // The input value flips to the raw form on the next render —
            // wait for that, then select-all so the cursor doesn't sit at
            // a stale offset measured against the abbreviated form.
            requestAnimationFrame(() => event.target.select());
          }}
          onBlur={() => setIsFocused(false)}
          onKeyDown={onKeyDown}
          onPaste={onPaste}
          inputMode="decimal"
          placeholder={derivedHint !== null ? formatHint(derivedHint) : ""}
          title={
            looksDerived
              ? `Likely derived (${fieldDef.derivedFrom?.join(" − ")}). Type to override.`
              : derivedHint !== null
                ? `Will be derived as ${formatHint(derivedHint)} on save.`
                : rawValue !== "" && rawValue !== displayValue
                  ? `Stored: ${rawValue}`
                  : undefined
          }
          className={cn(
            "h-6 w-full rounded-none border-0 bg-transparent px-1.5 text-[11px] tabular-nums",
            "focus:outline-none focus:ring-1 focus:ring-ring",
            looksDerived && "italic text-muted-foreground",
            saveState === "error" && "ring-1 ring-destructive",
          )}
        />
        {saveState !== "idle" && (
          <span className="pointer-events-none absolute right-1.5">
            <SaveIndicator state={saveState} className="text-[10px]" />
          </span>
        )}
      </div>
    </td>
  );
}

function derivedMatchesStored(
  fieldDef: FieldDef,
  row: FinancialRow,
  stored: string,
  ctx: DeriveContext,
): boolean {
  if (!fieldDef.derive) return false;
  const expected = fieldDef.derive(row, ctx);
  if (expected === null) return false;
  const storedNum = Number(stored);
  if (!Number.isFinite(storedNum)) return false;
  return Math.abs(expected - storedNum) < 1e-6;
}

function formatHint(value: number): string {
  if (Number.isInteger(value)) return value.toString();
  return value.toFixed(2).replace(/\.?0+$/, "");
}
