/**
 * Growth section — one mini-card per metric, each with:
 *   - title (e.g. "Revenue")
 *   - latest quarter's value as the headline number
 *   - YoY change badge (vs the same quarter 4 reports back)
 *   - footer with 3Y / 5Y / 10Y CAGRs pulled from the analysis payload
 *
 * Replaces the wide CAGR table — same data, much denser, easier to scan
 * across multiple metrics at once.
 */

import { ArrowDown, ArrowUp, Minus } from "lucide-react";
import { useMemo } from "react";

import { CollapsibleSection } from "@/components/CollapsibleSection";
import type { GrowthBlock } from "@/lib/analysis";
import { type FinancialRow, useFinancials } from "@/lib/financials";
import {
  useAbbreviatedFormat,
  useNumberFormat,
  usePercentFormat,
} from "@/lib/settings";
import { cn } from "@/lib/utils";

interface GrowthBarCardsProps {
  symbol: string;
  growth: GrowthBlock;
}

type FormatStyle = "currency" | "ratio";

interface MetricSpec {
  /** Key into FinancialRow for the per-quarter series. */
  field: keyof FinancialRow;
  /** Key into growth.metrics for the CAGR footer. */
  growthKey: string;
  label: string;
  /** How to render the headline + bars. `ratio` = no currency suffix, 2dp. */
  format: FormatStyle;
}

const METRICS: MetricSpec[] = [
  { field: "revenue", growthKey: "revenue", label: "Revenue", format: "currency" },
  { field: "operating_income", growthKey: "operating_income", label: "Operating Income", format: "currency" },
  { field: "ebitda", growthKey: "ebitda", label: "EBITDA", format: "currency" },
  { field: "net_income", growthKey: "net_income", label: "Net Income", format: "currency" },
  { field: "eps_diluted", growthKey: "eps_diluted", label: "EPS (diluted)", format: "ratio" },
  { field: "free_cash_flow", growthKey: "free_cash_flow", label: "Free Cash Flow", format: "currency" },
  { field: "total_equity", growthKey: "total_equity", label: "Total Equity", format: "currency" },
];

// Last N quarters shown in the sparkbars. Plenty for visual context
// without making each bar disappear into a pixel.
const HISTORY_QUARTERS = 40;

export function GrowthBarCards({ symbol, growth }: GrowthBarCardsProps) {
  const financialsQuery = useFinancials(symbol);
  const rows = useMemo(() => {
    const data = financialsQuery.data ?? [];
    // Sort ascending by period so the rightmost bar is the latest.
    return data.slice().sort((a, b) => a.period.localeCompare(b.period));
  }, [financialsQuery.data]);

  return (
    <CollapsibleSection title="Growth">
      {financialsQuery.isLoading ? (
        <p className="text-[11px] text-muted-foreground">Loading history…</p>
      ) : rows.length === 0 ? (
        <p className="text-[11px] text-muted-foreground">
          No quarterly history yet — import financials to populate this panel.
        </p>
      ) : (
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3 2xl:grid-cols-4">
          {METRICS.map((metric) => (
            <GrowthMetricCard
              key={metric.field}
              metric={metric}
              rows={rows}
              growth={growth}
            />
          ))}
        </div>
      )}
    </CollapsibleSection>
  );
}

// ─────────────────────────────────────────────────────────────────────
// One card
// ─────────────────────────────────────────────────────────────────────

function GrowthMetricCard({
  metric,
  rows,
  growth,
}: {
  metric: MetricSpec;
  rows: FinancialRow[];
  growth: GrowthBlock;
}) {
  const formatAbbreviated = useAbbreviatedFormat();
  const formatNumber = useNumberFormat();
  const formatPercent = usePercentFormat();

  // Series for the sparkbars (last N quarters, oldest → newest).
  const series = useMemo(() => {
    const all = rows.map((r) => toNumber(r[metric.field] as string | null));
    return all.slice(-HISTORY_QUARTERS);
  }, [rows, metric.field]);

  // Latest non-null value and the YoY comparison (4 quarters back).
  const headlineIdx = lastNonNullIndex(series);
  const headlineValue = headlineIdx >= 0 ? series[headlineIdx] : null;
  const yoyValue = headlineIdx >= 4 ? series[headlineIdx - 4] : null;
  const yoyChange =
    headlineValue !== null && yoyValue !== null && yoyValue !== 0
      ? ((headlineValue - yoyValue) / Math.abs(yoyValue)) * 100
      : null;
  const up = yoyChange !== null && yoyChange > 0;
  const down = yoyChange !== null && yoyChange < 0;

  const cagrs = growth.metrics[metric.growthKey] ?? {};

  function renderValue(v: number | null): string {
    if (v === null) return "—";
    if (metric.format === "ratio") {
      return formatNumber(v, { decimalPlaces: 2 });
    }
    return formatAbbreviated(v, { decimalPlaces: 2 });
  }

  return (
    <div className="rounded-md border border-border bg-card p-2.5">
      <header className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="text-[20px] font-semibold leading-tight tabular-nums text-primary">
            {renderValue(headlineValue)}
          </div>
          <div className="mt-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            {metric.label}
          </div>
        </div>
        {yoyChange !== null && (
          <span
            className={cn(
              "inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[10px] font-medium tabular-nums",
              up && "bg-success/15 text-success",
              down && "bg-destructive/15 text-destructive",
              !up && !down && "bg-muted/40 text-muted-foreground",
            )}
            title="Year-over-year change vs same quarter 4 reports back"
          >
            {up && <ArrowUp className="h-3 w-3" />}
            {down && <ArrowDown className="h-3 w-3" />}
            {!up && !down && <Minus className="h-3 w-3" />}
            {up && "+"}
            {formatPercent(yoyChange / 100)}
          </span>
        )}
      </header>

      <footer className="mt-2 flex items-center gap-2 text-[10px] text-muted-foreground">
        <StatChip label="3Y" value={cagrs["3Y"] ?? null} formatPercent={formatPercent} />
        <StatChip label="5Y" value={cagrs["5Y"] ?? null} formatPercent={formatPercent} />
        <StatChip label="10Y" value={cagrs["10Y"] ?? null} formatPercent={formatPercent} />
        <span
          className="ml-auto text-[9px] uppercase tracking-wide opacity-60"
          title="Compound annual growth rate (TTM-anchored) over the horizon"
        >
          CAGR
        </span>
      </footer>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────

function StatChip({
  label,
  value,
  formatPercent,
}: {
  label: string;
  value: number | null;
  formatPercent: (v: number | string | null | undefined, opts?: { fromFraction?: boolean; decimalPlaces?: number }) => string;
}) {
  const positive = value !== null && value > 0;
  const negative = value !== null && value < 0;
  return (
    <span className="inline-flex items-center gap-1">
      <span className="text-muted-foreground">{label} Avg</span>
      <span
        className={cn(
          "rounded bg-muted/30 px-1 py-px text-[10px] font-medium tabular-nums",
          value === null && "text-muted-foreground/60",
          positive && "text-success",
          negative && "text-destructive",
        )}
      >
        {value === null ? "—" : formatPercent(value, { fromFraction: true })}
      </span>
    </span>
  );
}

function toNumber(raw: string | null | undefined): number | null {
  if (raw === null || raw === undefined || raw === "") return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

function lastNonNullIndex(values: (number | null)[]): number {
  for (let i = values.length - 1; i >= 0; i -= 1) {
    if (values[i] !== null) return i;
  }
  return -1;
}
