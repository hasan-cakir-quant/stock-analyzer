/**
 * Reusable small "history" graph: one thin bar per period plus MA4 / MA8 /
 * MA12 moving-average lines. Data-prep wrappers (EPS, P/E, …) feed it a
 * `{ period, value }` series; this component owns the layout, MA math,
 * theming, and empty/loading states so every graph in the section matches.
 */

import { Maximize2 } from "lucide-react";
import { useState } from "react";
import {
  Bar,
  Cell,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Modal } from "@/components/Modal";
import { useAbbreviatedFormat, useNumberFormat } from "@/lib/settings";

import { clampToWindow, useMaxQuarters } from "./graphsFilter";

export interface HistoryPoint {
  period: string;
  value: number | null;
}

/** Placeholder card for a graph that doesn't apply to this stock (e.g. EV
 * multiples on a bank). Keeps the grid layout consistent. */
export function NotApplicableGraph({ title, reason }: { title: string; reason: string }) {
  return (
    <section className="rounded-md border border-border bg-card text-card-foreground shadow-sm">
      <header className="flex items-center justify-between border-b border-border px-2 py-1">
        <h3 className="truncate text-[11px] font-medium">{title}</h3>
        <span className="text-[9px] text-muted-foreground">n/a</span>
      </header>
      <div className="flex h-[180px] items-center justify-center px-3 text-center text-[10px] text-muted-foreground">
        {reason}
      </div>
    </section>
  );
}

interface InternalPoint extends HistoryPoint {
  [maKey: string]: string | number | null;
}

/** Moving-average lines to overlay: window length, data key, label, color. */
const MOVING_AVERAGES = [
  { window: 4, key: "ma4", label: "MA4", color: "hsl(199, 89%, 48%)" },
  { window: 8, key: "ma8", label: "MA8", color: "hsl(var(--warning))" },
  { window: 12, key: "ma12", label: "MA12", color: "hsl(280, 65%, 60%)" },
] as const;

const MA_LABEL: Record<string, string> = Object.fromEntries(
  MOVING_AVERAGES.map((m) => [m.key, m.label]),
);

interface HistoryBarChartProps {
  title: string;
  /** Tooltip series name for the value, e.g. "EPS" or "P/E". */
  valueName: string;
  data: HistoryPoint[];
  isLoading?: boolean;
  emptyText?: string;
  /** Decimals for the Y axis / tooltip value. Default 2. */
  decimalPlaces?: number;
  /** Color negative bars with the destructive hue (EPS can go negative). */
  highlightNegative?: boolean;
  /** Abbreviate large values (e.g. 1.2B) for currency series like EBITDA. */
  abbreviate?: boolean;
}

/** Simple moving average over `window` periods; null until a full window of finite values. */
function movingAverageAt(points: HistoryPoint[], i: number, window: number): number | null {
  if (i < window - 1) return null;
  const slice = points.slice(i - window + 1, i + 1).map((q) => q.value);
  if (!slice.every((v) => v !== null && Number.isFinite(v))) return null;
  return (slice as number[]).reduce((acc, v) => acc + v, 0) / window;
}

function withMovingAverages(points: HistoryPoint[]): InternalPoint[] {
  return points.map((p, i) => {
    const row: InternalPoint = { ...p };
    for (const ma of MOVING_AVERAGES) {
      row[ma.key] = movingAverageAt(points, i, ma.window);
    }
    return row;
  });
}

export function HistoryBarChart({
  title,
  valueName,
  data,
  isLoading = false,
  emptyText = "No history yet.",
  decimalPlaces = 2,
  highlightNegative = false,
  abbreviate = false,
}: HistoryBarChartProps) {
  const formatNumber = useNumberFormat();
  const formatAbbreviated = useAbbreviatedFormat();
  const formatValue = (v: number) =>
    abbreviate ? formatAbbreviated(v) : formatNumber(v, { decimalPlaces });
  const maxQuarters = useMaxQuarters();
  // MAs are computed over the *full* history, then we trim to the selected
  // window so the visible moving-average lines stay correct at the left edge.
  const points = clampToWindow(withMovingAverages(data), maxQuarters);
  const hasAny = points.some((d) => d.value !== null && Number.isFinite(d.value));
  const [expanded, setExpanded] = useState(false);

  function renderChart(height: number, big: boolean) {
    if (isLoading) {
      return <p className="py-4 text-center text-[10px] text-muted-foreground">Loading…</p>;
    }
    if (!hasAny) {
      return <p className="py-4 text-center text-[10px] text-muted-foreground">{emptyText}</p>;
    }
    const fontSize = big ? 11 : 8;
    return (
      <div style={{ width: "100%", height }}>
        <ResponsiveContainer>
          <ComposedChart data={points} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <XAxis
              dataKey="period"
              tick={{ fontSize, fill: "hsl(var(--muted-foreground))" }}
              stroke="hsl(var(--border))"
              interval="preserveStartEnd"
              minTickGap={big ? 28 : 16}
            />
            <YAxis
              tick={{ fontSize, fill: "hsl(var(--muted-foreground))" }}
              stroke="hsl(var(--border))"
              width={abbreviate ? (big ? 56 : 40) : big ? 40 : 26}
              tickFormatter={(v: number) => formatValue(v)}
            />
            <Tooltip
              cursor={{ fill: "hsl(var(--accent) / 0.4)" }}
              contentStyle={{
                backgroundColor: "hsl(var(--card))",
                border: "1px solid hsl(var(--border))",
                fontSize: big ? 12 : 10,
              }}
              labelStyle={{ color: "hsl(var(--foreground))" }}
              itemStyle={{ color: "hsl(var(--foreground))" }}
              formatter={(value: number, name: string) => [
                formatValue(value),
                MA_LABEL[name] ?? valueName,
              ]}
            />
            <Bar
              dataKey="value"
              radius={[1, 1, 0, 0]}
              maxBarSize={big ? 14 : 5}
              isAnimationActive={false}
            >
              {points.map((entry, i) => (
                <Cell
                  key={i}
                  fill={
                    highlightNegative && entry.value !== null && entry.value < 0
                      ? "hsl(var(--destructive))"
                      : "hsl(var(--primary))"
                  }
                />
              ))}
            </Bar>
            {MOVING_AVERAGES.map((ma) => (
              <Line
                key={ma.key}
                type="monotone"
                dataKey={ma.key}
                name={ma.key}
                stroke={ma.color}
                strokeWidth={big ? 1.75 : 1.25}
                dot={false}
                isAnimationActive={false}
                connectNulls
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    );
  }

  const legend = (
    <div className="flex items-center gap-1.5">
      {MOVING_AVERAGES.map((ma) => (
        <span key={ma.key} className="flex items-center gap-0.5 text-[8px] text-muted-foreground">
          <span className="inline-block h-0.5 w-2" style={{ backgroundColor: ma.color }} />
          {ma.label}
        </span>
      ))}
      <span className="text-[9px] text-muted-foreground">{points.length}q</span>
    </div>
  );

  return (
    <>
      <section className="rounded-md border border-border bg-card text-card-foreground shadow-sm">
        <header className="flex flex-wrap items-center justify-between gap-x-1.5 border-b border-border px-2 py-1">
          <h3 className="truncate text-[11px] font-medium">{title}</h3>
          <div className="flex items-center gap-1.5">
            {legend}
            <button
              type="button"
              onClick={() => setExpanded(true)}
              title="Expand"
              className="rounded p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground"
            >
              <Maximize2 className="h-3 w-3" />
            </button>
          </div>
        </header>
        <div className="px-1.5 py-1">{renderChart(180, false)}</div>
      </section>

      <Modal
        open={expanded}
        onClose={() => setExpanded(false)}
        className="max-w-4xl"
        title={
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold">{title}</span>
            {legend}
          </div>
        }
      >
        {renderChart(460, true)}
      </Modal>
    </>
  );
}
