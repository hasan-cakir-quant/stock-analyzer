/**
 * Data Availability — at-a-glance coverage of every tracked stock: how many
 * quarters of financials are stored, the latest reported quarter, whether that
 * quarter has an end-of-quarter closing price, and whether a live current
 * price / beta is on file.
 *
 * Each row has a Refresh button (incremental top-up: adds only quarters newer
 * than the latest stored one, fetches their closing prices, and refreshes the
 * live price/beta). "Refresh all" runs that across every stock sequentially.
 */

import { Check, Database, ListPlus, Loader2, Play, RefreshCw, Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { JobsPanel } from "@/features/jobs/JobsPanel";
import {
  type DataAvailabilityItem,
  useDataAvailability,
  useRefreshStock,
  useRunStockJob,
  useSeedSp500,
} from "@/lib/dataAvailability";
import type { JobType } from "@/lib/jobs";
import { useCurrencyFormat } from "@/lib/settings";
import { useToast } from "@/stores/toast";
import { cn } from "@/lib/utils";

// Per-stock job columns: button + last-updated timestamp.
const JOB_COLUMNS: {
  type: JobType;
  label: string;
  pick: (r: DataAvailabilityItem) => string | null;
}[] = [
  { type: "financials", label: "Financials", pick: (r) => r.financials_updated_at },
  { type: "prices", label: "Price & β", pick: (r) => r.price_updated_at },
  { type: "fair_values", label: "Fair values", pick: (r) => r.fair_values_at },
  { type: "grades", label: "Grades", pick: (r) => r.grades_at },
];

const JOB_LABELS: Record<JobType, string> = {
  financials: "Fetch financials",
  prices: "Fetch price & beta",
  fair_values: "Compute fair values",
  grades: "Compute grades",
};

function fmtWhen(iso: string | null): string {
  if (!iso) return "never";
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function DataAvailability() {
  const query = useDataAvailability();
  const refresh = useRefreshStock();
  const runStockJob = useRunStockJob();
  const seedSp500 = useSeedSp500();
  const toast = useToast();

  const [filter, setFilter] = useState("");
  const [busySymbol, setBusySymbol] = useState<string | null>(null);
  const [busyJobs, setBusyJobs] = useState<Set<string>>(new Set());
  const [refreshingAll, setRefreshingAll] = useState(false);

  async function runJob(symbol: string, type: JobType) {
    const key = `${symbol}:${type}`;
    setBusyJobs((prev) => new Set(prev).add(key));
    try {
      const res = await runStockJob.mutateAsync({ symbol, jobType: type });
      toast.show(
        res.ok
          ? `${symbol}: ${JOB_LABELS[type]} done.`
          : `${symbol}: ${JOB_LABELS[type]} — nothing to do (no data).`,
        { tone: res.ok ? "success" : "error" },
      );
    } catch (err) {
      toast.show(
        err instanceof Error
          ? `${symbol}: ${err.message}`
          : `${symbol}: ${JOB_LABELS[type]} failed.`,
        { tone: "error" },
      );
    } finally {
      setBusyJobs((prev) => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  }

  const items = useMemo(() => query.data ?? [], [query.data]);
  const visible = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!needle) return items;
    return items.filter((i) =>
      `${i.symbol} ${i.category ?? ""}`.toLowerCase().includes(needle),
    );
  }, [items, filter]);

  /** Refresh one stock. Returns true on success. `quiet` skips the success
   * toast (used by Refresh all, which shows a single summary instead). */
  async function refreshOne(symbol: string, quiet = false): Promise<boolean> {
    setBusySymbol(symbol);
    try {
      const res = await refresh.mutateAsync(symbol);
      const fin = res.steps.financials;
      if (!fin?.ok) {
        toast.show(`${symbol}: ${fin?.detail ?? "refresh failed"}`, { tone: "error" });
        return false;
      }
      if (!quiet) {
        const written = fin.written ?? 0;
        toast.show(
          written > 0
            ? `${symbol}: added ${written} new quarter${written === 1 ? "" : "s"}.`
            : `${symbol}: already up to date.`,
          { tone: "success" },
        );
      }
      return true;
    } catch (err) {
      toast.show(
        err instanceof Error ? `${symbol}: ${err.message}` : `${symbol}: refresh failed.`,
        { tone: "error" },
      );
      return false;
    } finally {
      setBusySymbol(null);
    }
  }

  async function handleSeedSp500() {
    try {
      const res = await seedSp500.mutateAsync();
      toast.show(
        res.created > 0
          ? `Added ${res.created} S&P 500 stock${res.created === 1 ? "" : "s"}${
              res.skipped ? ` (${res.skipped} already tracked)` : ""
            }.`
          : `All ${res.total} S&P 500 stocks are already tracked.`,
        { tone: "success" },
      );
    } catch (err) {
      toast.show(
        err instanceof Error ? `Couldn't add S&P 500 — ${err.message}` : "Couldn't add S&P 500.",
        { tone: "error" },
      );
    }
  }

  async function handleRefreshAll() {
    if (items.length === 0) return;
    setRefreshingAll(true);
    let ok = 0;
    let fail = 0;
    // Sequential — back-to-back hits on Yahoo/SEC get throttled.
    for (const item of items) {
      const success = await refreshOne(item.symbol, true);
      if (success) ok += 1;
      else fail += 1;
    }
    setRefreshingAll(false);
    toast.show(`Refresh all done — ${ok} ok${fail ? `, ${fail} failed` : ""}.`, {
      tone: fail ? "error" : "success",
    });
  }

  return (
    <section className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <Database className="h-4 w-4 text-primary" />
          <h1 className="text-lg font-semibold tracking-tight">Data availability</h1>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => void handleSeedSp500()}
            disabled={seedSp500.isPending || refreshingAll}
            title="Create empty USD shells for every S&P 500 constituent (no data fetched)"
            className="inline-flex items-center gap-1 rounded-md border border-border bg-secondary px-2.5 py-1 text-xs font-medium text-secondary-foreground hover:bg-accent disabled:opacity-50"
          >
            <ListPlus className="h-3.5 w-3.5" />
            {seedSp500.isPending ? "Adding S&P 500…" : "Add S&P 500"}
          </button>
          <button
            type="button"
            onClick={() => void handleRefreshAll()}
            disabled={refreshingAll || busySymbol !== null || items.length === 0}
            className="inline-flex items-center gap-1 rounded-md bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", refreshingAll && "animate-spin")} />
            {refreshingAll ? "Refreshing all…" : "Refresh all"}
          </button>
        </div>
      </div>

      <p className="text-[11px] text-muted-foreground">
        Refresh adds only quarters newer than the latest stored one, fetches their
        closing prices, and refreshes the live price &amp; beta.
      </p>

      <JobsPanel />

      <div className="flex flex-wrap items-center gap-1.5">
        <div className="relative max-w-xs flex-1">
          <Search className="pointer-events-none absolute left-1.5 top-1/2 h-3 w-3 -translate-y-1/2 text-muted-foreground" />
          <input
            type="search"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter symbol or category…"
            className="h-7 w-full rounded-md border border-input bg-background pl-6 pr-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <span className="text-[10px] text-muted-foreground">
          {visible.length} of {items.length}
        </span>
      </div>

      {query.isLoading ? (
        <p className="text-[11px] text-muted-foreground">Loading…</p>
      ) : query.isError ? (
        <p className="text-[11px] text-destructive">
          Couldn't load data availability. {(query.error as Error).message}
        </p>
      ) : visible.length === 0 ? (
        <p className="rounded-md border border-dashed border-border bg-card/40 p-3 text-[11px] text-muted-foreground">
          {items.length === 0 ? "No stocks tracked yet." : "No matches for that filter."}
        </p>
      ) : (
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full border-separate border-spacing-0 text-[11px]">
            <thead className="bg-card">
              <tr className="text-muted-foreground">
                <Th>Symbol</Th>
                <Th>Cur</Th>
                <Th>Category</Th>
                <Th align="right">Quarters</Th>
                <Th>Latest quarter</Th>
                <Th align="center">Latest close</Th>
                <Th align="right">Closes</Th>
                <Th align="right">Current price</Th>
                <Th align="right">Beta</Th>
                {JOB_COLUMNS.map((c) => (
                  <Th key={c.type} align="center">
                    {c.label}
                  </Th>
                ))}
                <Th align="right">All</Th>
              </tr>
            </thead>
            <tbody>
              {visible.map((row) => (
                <Row
                  key={row.symbol}
                  row={row}
                  busy={busySymbol === row.symbol}
                  disabled={refreshingAll || busySymbol !== null}
                  busyJobs={busyJobs}
                  onRunJob={(type) => void runJob(row.symbol, type)}
                  onRefresh={() => void refreshOne(row.symbol)}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------

function Th({
  children,
  align = "left",
}: {
  children: React.ReactNode;
  align?: "left" | "right" | "center";
}) {
  return (
    <th
      className={cn(
        "border-b border-border px-2 py-1 font-medium",
        align === "right" && "text-right",
        align === "center" && "text-center",
        align === "left" && "text-left",
      )}
    >
      {children}
    </th>
  );
}

function Row({
  row,
  busy,
  disabled,
  busyJobs,
  onRunJob,
  onRefresh,
}: {
  row: DataAvailabilityItem;
  busy: boolean;
  disabled: boolean;
  busyJobs: Set<string>;
  onRunJob: (type: JobType) => void;
  onRefresh: () => void;
}) {
  const formatCurrency = useCurrencyFormat();
  const hasFinancials = row.quarters_count > 0;

  return (
    <tr className="border-t border-border/60 hover:bg-accent/40">
      <td className="px-2 py-1 align-middle">
        <Link
          to={`/stocks/${encodeURIComponent(row.symbol)}`}
          className="font-mono font-medium text-foreground hover:text-primary"
        >
          {row.symbol}
        </Link>
      </td>
      <td className="px-2 py-1 align-middle text-muted-foreground">{row.currency}</td>
      <td className="px-2 py-1 align-middle text-muted-foreground">
        {row.category ?? <span className="italic">—</span>}
      </td>
      <td
        className={cn(
          "px-2 py-1 text-right align-middle tabular-nums",
          !hasFinancials && "text-destructive",
        )}
      >
        {hasFinancials ? row.quarters_count : "none"}
      </td>
      <td className="px-2 py-1 align-middle tabular-nums">
        {row.latest_quarter ?? <span className="text-muted-foreground">—</span>}
        {row.latest_quarter_end_date && (
          <span className="ml-1 text-[9px] text-muted-foreground">
            ({row.latest_quarter_end_date})
          </span>
        )}
      </td>
      <td className="px-2 py-1 text-center align-middle">
        {hasFinancials ? <YesNo ok={row.latest_quarter_has_close} /> : <Dash />}
      </td>
      <td className="px-2 py-1 text-right align-middle tabular-nums text-muted-foreground">
        {hasFinancials ? `${row.closing_price_count}/${row.quarters_count}` : "—"}
      </td>
      <td className="px-2 py-1 text-right align-middle tabular-nums">
        {row.has_current_price && row.current_price !== null ? (
          formatCurrency(Number(row.current_price), row.currency)
        ) : (
          <span className="inline-flex items-center gap-0.5 text-muted-foreground">
            <X className="h-3 w-3" /> none
          </span>
        )}
      </td>
      <td className="px-2 py-1 text-right align-middle tabular-nums text-muted-foreground">
        {row.beta !== null ? Number(row.beta).toFixed(2) : "—"}
      </td>
      {JOB_COLUMNS.map((c) => {
        const jobBusy = busyJobs.has(`${row.symbol}:${c.type}`);
        const when = c.pick(row);
        return (
          <td key={c.type} className="px-2 py-1 text-center align-middle">
            <div className="flex flex-col items-center gap-0.5">
              <button
                type="button"
                onClick={() => onRunJob(c.type)}
                disabled={jobBusy || disabled}
                title={`${JOB_LABELS[c.type]} for ${row.symbol}`}
                className="inline-flex items-center gap-1 rounded-md border border-border bg-secondary px-1.5 py-0.5 text-[10px] text-secondary-foreground hover:bg-accent disabled:opacity-50"
              >
                {jobBusy ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <Play className="h-3 w-3" />
                )}
                Run
              </button>
              <span
                className={cn(
                  "text-[9px] tabular-nums",
                  when ? "text-muted-foreground" : "text-muted-foreground/50",
                )}
              >
                {fmtWhen(when)}
              </span>
            </div>
          </td>
        );
      })}
      <td className="px-2 py-1 text-right align-middle">
        <button
          type="button"
          onClick={onRefresh}
          disabled={disabled}
          title="Combined: new quarters + closes + price & beta"
          className="inline-flex items-center gap-1 rounded-md border border-border bg-secondary px-1.5 py-0.5 text-[10px] text-secondary-foreground hover:bg-accent disabled:opacity-50"
        >
          <RefreshCw className={cn("h-3 w-3", busy && "animate-spin")} />
          {busy ? "…" : "Refresh"}
        </button>
      </td>
    </tr>
  );
}

function YesNo({ ok }: { ok: boolean }) {
  return ok ? (
    <Check className="mx-auto h-3.5 w-3.5 text-success" />
  ) : (
    <X className="mx-auto h-3.5 w-3.5 text-destructive" />
  );
}

function Dash() {
  return <span className="text-muted-foreground">—</span>;
}
