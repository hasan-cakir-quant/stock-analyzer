/**
 * ImportFinancialsDialog — load financial data from a supported source
 * (SEC EDGAR live fetch, or a JSON file for file-based parsers) into the
 * grid via the same bulk-upsert path the per-cell saves use.
 *
 * Flow:
 *   1. Pick a parser (source × statement) from the dropdown.
 *   2. For file-based sources: pick the file. For EDGAR: ensure the
 *      stock's CIK is on file (Look-up button is right there if not).
 *   3. Click "Parse" / "Fetch from EDGAR" → server returns a preview
 *      (rows, unmapped labels, warnings).
 *   4. Review the preview table.
 *   5. Click "Save N quarters" → bulk-upsert.
 */

import { useMemo, useState } from "react";

import { Modal } from "@/components/Modal";
import {
  type BulkUpsertRow,
  type ImportPreview,
  type ImportSource,
  useBulkUpsertFinancials,
  useImportFromEdgar,
  useImportPreview,
  useImportSources,
} from "@/lib/financials";
import { useAbbreviatedFormat } from "@/lib/settings";
import { useLookupCik, useStock, useUpdateStock } from "@/lib/stocks";
import { cn } from "@/lib/utils";
import { useToast } from "@/stores/toast";

interface ImportHtmlDialogProps {
  symbol: string;
  open: boolean;
  onClose: () => void;
}

export function ImportHtmlDialog({ symbol, open, onClose }: ImportHtmlDialogProps) {
  const sourcesQuery = useImportSources();
  const previewMutation = useImportPreview(symbol);
  const edgarMutation = useImportFromEdgar(symbol);
  const bulkUpsert = useBulkUpsertFinancials(symbol);
  const stockQuery = useStock(symbol);
  const updateStock = useUpdateStock(symbol);
  const lookupCik = useLookupCik(symbol);
  const toast = useToast();

  const [parserId, setParserId] = useState<string>("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saveCaptionAsUnits, setSaveCaptionAsUnits] = useState(true);

  const stockHasNoUnitsNote = !stockQuery.data?.units_note;
  const captionAvailable = Boolean(preview?.caption);
  const offerCaptionSave = stockHasNoUnitsNote && captionAvailable;

  const sources = sourcesQuery.data ?? [];
  const selectedSource = sources.find((s) => s.id === parserId) ?? null;
  const isEdgar = selectedSource?.source === "sec_edgar";
  const cikOnFile = Boolean(stockQuery.data?.cik);
  const parsing = previewMutation.isPending || edgarMutation.isPending;

  // Default to the first parser the moment the catalogue loads.
  if (parserId === "" && sources.length > 0) {
    setParserId(sources[0].id);
  }

  function reset() {
    setFile(null);
    setPreview(null);
    setError(null);
    previewMutation.reset();
    edgarMutation.reset();
    bulkUpsert.reset();
  }

  function handleClose() {
    if (parsing || bulkUpsert.isPending) return;
    reset();
    onClose();
  }

  async function handleLookupCik() {
    setError(null);
    try {
      await lookupCik.mutateAsync();
      toast.show("CIK resolved", { tone: "success" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "CIK lookup failed.");
    }
  }

  async function handleParse(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPreview(null);
    if (!parserId) {
      setError("Choose a source.");
      return;
    }
    try {
      if (isEdgar) {
        if (!cikOnFile) {
          setError("This stock has no CIK on file — look it up first.");
          return;
        }
        const result = await edgarMutation.mutateAsync();
        setPreview(result);
      } else {
        if (!file) {
          setError("Pick a source file.");
          return;
        }
        const result = await previewMutation.mutateAsync({ parserId, file });
        setPreview(result);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Parse failed.");
    }
  }

  async function handleSave() {
    if (!preview) return;
    setError(null);
    try {
      const rows: BulkUpsertRow[] = preview.rows.map((row) => ({
        period: row.period,
        // Persist the source's period_end_date so the user can later
        // verify our quarter mapping was right.
        ...(row.period_end_date ? { period_end_date: row.period_end_date } : {}),
        ...row.fields,
        // Forward the full source-label payload — the backend archives
        // it to `financial_imports` for fields we don't yet have a
        // schema column for.
        ...(Object.keys(row.raw_source).length > 0
          ? { raw_source: row.raw_source }
          : {}),
      }));
      const result = await bulkUpsert.mutateAsync({
        rows,
        importContext: {
          parser_id: preview.parser_id,
          source: preview.source,
          statement: preview.statement,
          caption: preview.caption,
        },
      });
      // Optionally stamp the source's caption onto the stock so the units
      // convention is permanently visible in the data-entry header.
      if (offerCaptionSave && saveCaptionAsUnits && preview.caption) {
        try {
          await updateStock.mutateAsync({ units_note: preview.caption });
        } catch {
          // Non-fatal — the data still saved; just warn.
          toast.show("Imported, but couldn't save units note", { tone: "error" });
        }
      }
      toast.show(`Imported ${result.written} quarters`, { tone: "success" });
      reset();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed.");
    }
  }

  return (
    <Modal open={open} onClose={handleClose} title="Import financials" className="max-w-3xl">
      <form onSubmit={handleParse} className="space-y-2">
        <SourceSelect
          sources={sources}
          loading={sourcesQuery.isLoading}
          value={parserId}
          onChange={setParserId}
        />
        {isEdgar ? (
          <EdgarSourcePanel
            cik={stockQuery.data?.cik ?? null}
            symbol={symbol}
            onLookupCik={handleLookupCik}
            lookingUp={lookupCik.isPending}
          />
        ) : (
          <FilePicker file={file} onChange={setFile} />
        )}
        <div className="flex items-center justify-between gap-2 pt-0.5">
          <p className="text-[10px] text-muted-foreground">
            {isEdgar
              ? "EDGAR values are already in absolute US$; Q4 is derived from 10-K when only annual is filed."
              : "Numbers are parsed in the source's own units (e.g. millions). Saving uses the same upsert path as manual edits — derivations apply."}
          </p>
          <button
            type="submit"
            disabled={!parserId || (isEdgar ? !cikOnFile : !file) || parsing}
            className="inline-flex items-center gap-1 rounded-md bg-secondary px-2.5 py-1 text-[11px] font-medium text-secondary-foreground hover:bg-accent disabled:opacity-50"
          >
            {parsing ? "Fetching…" : isEdgar ? "Fetch from EDGAR" : "Parse"}
          </button>
        </div>
      </form>

      {error && (
        <p role="alert" className="mt-2 text-[11px] text-destructive">
          {error}
        </p>
      )}

      {preview && <PreviewSection preview={preview} />}

      {preview && (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-2">
          {offerCaptionSave ? (
            <label className="flex items-start gap-1.5 text-[10px] text-muted-foreground">
              <input
                type="checkbox"
                checked={saveCaptionAsUnits}
                onChange={(e) => setSaveCaptionAsUnits(e.target.checked)}
                className="mt-0.5"
              />
              <span>
                Save the source caption as the stock's units note:{" "}
                <span className="text-foreground">"{preview.caption}"</span>
              </span>
            </label>
          ) : (
            <span />
          )}
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={handleClose}
              disabled={bulkUpsert.isPending}
              className="rounded-md border border-border bg-secondary px-2.5 py-1 text-[11px] text-secondary-foreground hover:bg-accent disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={preview.rows.length === 0 || bulkUpsert.isPending}
              className="rounded-md bg-primary px-2.5 py-1 text-[11px] font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              {bulkUpsert.isPending
                ? "Saving…"
                : `Save ${preview.rows.length} quarter${preview.rows.length === 1 ? "" : "s"}`}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}

// ---------------------------------------------------------------------------

function SourceSelect({
  sources,
  loading,
  value,
  onChange,
}: {
  sources: ImportSource[];
  loading: boolean;
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <label htmlFor="import-source" className="text-[11px] text-muted-foreground">
        Source &amp; statement
      </label>
      <select
        id="import-source"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={loading}
        className="h-7 w-full rounded-md border border-input bg-background px-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
      >
        {loading ? (
          <option>Loading…</option>
        ) : sources.length === 0 ? (
          <option>No parsers registered</option>
        ) : (
          sources.map((s) => (
            <option key={s.id} value={s.id}>
              {s.label}
            </option>
          ))
        )}
      </select>
    </div>
  );
}

function EdgarSourcePanel({
  cik,
  symbol,
  onLookupCik,
  lookingUp,
}: {
  cik: string | null;
  symbol: string;
  onLookupCik: () => void;
  lookingUp: boolean;
}) {
  return (
    <div className="flex flex-col gap-1 rounded-md border border-border bg-card/40 p-2">
      <div className="flex items-center justify-between gap-2">
        <div className="flex flex-col leading-tight">
          <span className="text-[11px] text-muted-foreground">SEC EDGAR CIK</span>
          <span className="font-mono text-xs text-foreground">
            {cik ?? <span className="text-destructive">— not set —</span>}
          </span>
        </div>
        <button
          type="button"
          onClick={onLookupCik}
          disabled={lookingUp}
          className="inline-flex items-center gap-1 rounded-md border border-border bg-secondary px-2 py-0.5 text-[11px] text-secondary-foreground hover:bg-accent disabled:opacity-50"
        >
          {lookingUp ? "Looking up…" : cik ? "Re-lookup" : "Look up CIK"}
        </button>
      </div>
      {!cik && (
        <p className="text-[10px] text-destructive">
          A CIK is required to fetch from EDGAR. Click "Look up CIK" to resolve
          one for {symbol} from SEC's ticker registry.
        </p>
      )}
    </div>
  );
}

function FilePicker({
  file,
  onChange,
}: {
  file: File | null;
  onChange: (next: File | null) => void;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <label htmlFor="import-file" className="text-[11px] text-muted-foreground">
        Source file (JSON)
      </label>
      <div className="flex items-center gap-2">
        <input
          id="import-file"
          type="file"
          accept=".json,application/json"
          onChange={(e) => onChange(e.target.files?.[0] ?? null)}
          className="block text-[11px] text-muted-foreground file:mr-2 file:cursor-pointer file:rounded-md file:border-0 file:bg-secondary file:px-1.5 file:py-0.5 file:text-[11px] file:text-secondary-foreground file:hover:bg-accent"
        />
        {file && (
          <span className="text-[10px] text-muted-foreground">
            {file.name} ({Math.round(file.size / 1024)} KB)
          </span>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------

function PreviewSection({ preview }: { preview: ImportPreview }) {
  const formatAbbreviated = useAbbreviatedFormat();

  // Compute the union of fields touched across all rows so the table has
  // a stable column order regardless of which quarters covered which lines.
  const fieldOrder = useMemo(() => {
    const seen: string[] = [];
    const set = new Set<string>();
    for (const row of preview.rows) {
      for (const f of Object.keys(row.fields)) {
        if (!set.has(f)) {
          set.add(f);
          seen.push(f);
        }
      }
    }
    return seen;
  }, [preview]);

  return (
    <section className="mt-3 space-y-2">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-xs font-medium">
          Preview — {preview.rows.length} quarter{preview.rows.length === 1 ? "" : "s"}, {fieldOrder.length} fields
        </h3>
        {preview.caption && (
          <span className="text-[10px] text-muted-foreground">{preview.caption}</span>
        )}
      </header>

      {preview.warnings.length > 0 && (
        <div className="rounded-md border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">
          {preview.warnings.map((w, i) => (
            <div key={i}>{w}</div>
          ))}
        </div>
      )}

      {preview.rows.length === 0 ? (
        <p className="text-[11px] text-muted-foreground">
          The parser couldn't find any rows in this file.
        </p>
      ) : (
        <div className="max-h-72 overflow-auto rounded-md border border-border">
          <table className="w-full border-separate border-spacing-0 text-[11px]">
            <thead className="sticky top-0 bg-card">
              <tr>
                <th className="sticky left-0 z-10 bg-card px-2 py-1 text-left font-medium text-muted-foreground">
                  Quarter
                </th>
                {fieldOrder.map((field) => (
                  <th
                    key={field}
                    className="border-l border-border px-2 py-1 text-right font-medium"
                  >
                    {field}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {preview.rows.map((row) => (
                <tr key={row.period} className="border-t border-border">
                  <th
                    scope="row"
                    className="sticky left-0 z-10 bg-card px-2 py-0.5 text-left font-mono text-foreground"
                  >
                    {row.period}
                    {row.period_end_date && (
                      <span className="ml-1 text-[9px] text-muted-foreground">
                        ({row.period_end_date})
                      </span>
                    )}
                  </th>
                  {fieldOrder.map((field) => {
                    const raw = row.fields[field];
                    return (
                      <td
                        key={field}
                        title={raw !== undefined ? `Stored: ${raw}` : undefined}
                        className={cn(
                          "border-l border-t border-border px-2 py-0.5 text-right tabular-nums",
                          raw === undefined && "text-muted-foreground/40",
                        )}
                      >
                        {raw !== undefined ? formatAbbreviated(raw) : "—"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {preview.unmapped_labels.length > 0 && (
        <details className="text-[11px]">
          <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
            {preview.unmapped_labels.length} line item
            {preview.unmapped_labels.length === 1 ? "" : "s"} not recognised
          </summary>
          <ul className="mt-1 list-disc pl-5 text-muted-foreground">
            {preview.unmapped_labels.map((label) => (
              <li key={label}>{label}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

