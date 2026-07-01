/**
 * Distribution of the MA-valuation fair values for the *currently selected
 * scenario*. Every cell in the MA-valuation table (each method × MA4/MA8/MA12)
 * is one estimate of fair value per share; this histogram shows how those
 * estimates are spread out, so you can see where they cluster and how tight
 * the consensus is. The latest price is overlaid as a reference line.
 *
 * Recomputes whenever the scenario changes (pessimist/normal/optimist scale
 * every fair value), so the shape shifts with the chosen scenario.
 */

import {
  Bar,
  BarChart,
  Cell,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useAbbreviatedFormat, useCurrencyFormat } from "@/lib/settings";

import type { ValueArea } from "./valueArea";

interface FairValueDistributionChartProps {
  /** All computable fair values across methods/windows for the scenario. */
  values: number[];
  /** Central 70% value area of `values`; its mean is the headline fair value. */
  valueArea: ValueArea | null;
  currentPrice: number | null;
  currency: string | null;
  scenarioLabel: string;
}

const BIN_COUNT = 8;

interface Bin {
  idx: number;
  start: number;
  end: number;
  center: number;
  count: number;
}

function buildBins(values: number[], extra: number[]): Bin[] {
  // Include the reference markers (e.g. current price) in the domain so they
  // always land inside the chart.
  const all = [...values, ...extra];
  const min = Math.min(...all);
  const max = Math.max(...all);
  const span = max - min || Math.abs(min) || 1;
  const lo = max === min ? min - span / 2 : min;
  const width = (max === min ? span : max - min) / BIN_COUNT;

  const bins: Bin[] = Array.from({ length: BIN_COUNT }, (_, idx) => ({
    idx,
    start: lo + idx * width,
    end: lo + (idx + 1) * width,
    center: lo + (idx + 0.5) * width,
    count: 0,
  }));
  for (const v of values) {
    let idx = Math.floor((v - lo) / width);
    if (idx < 0) idx = 0;
    if (idx >= BIN_COUNT) idx = BIN_COUNT - 1;
    bins[idx].count += 1;
  }
  return bins;
}

/** Category index of the bin that contains `value`. */
function binIndexOf(bins: Bin[], value: number): number | null {
  for (const b of bins) {
    if (value >= b.start && value <= b.end) return b.idx;
  }
  if (value < bins[0].start) return bins[0].idx;
  if (value > bins[bins.length - 1].end) return bins[bins.length - 1].idx;
  return null;
}

export function FairValueDistributionChart({
  values,
  valueArea,
  currentPrice,
  currency,
  scenarioLabel,
}: FairValueDistributionChartProps) {
  const formatAbbreviated = useAbbreviatedFormat();
  const formatCurrency = useCurrencyFormat();

  // Upside/downside of the value-area mean vs the latest price.
  const meanUpside =
    valueArea !== null && currentPrice !== null && currentPrice > 0
      ? ((valueArea.mean - currentPrice) / currentPrice) * 100
      : null;

  const card = (children: React.ReactNode) => (
    <section className="rounded-md border border-border bg-card text-card-foreground shadow-sm">
      <header className="flex flex-wrap items-center justify-between gap-x-2 border-b border-border px-2 py-1">
        <h4 className="truncate text-[10px] font-medium">
          Fair value distribution — {scenarioLabel}
        </h4>
        {valueArea ? (
          <span className="text-[9px] text-muted-foreground">
            VA{" "}
            <span className="tabular-nums text-foreground">
              {formatCurrency(valueArea.low, currency)}–
              {formatCurrency(valueArea.high, currency)}
            </span>{" "}
            · mean{" "}
            <span className="font-medium tabular-nums text-primary">
              {formatCurrency(valueArea.mean, currency)}
            </span>
            {meanUpside !== null && (
              <>
                {" "}
                ·{" "}
                <span
                  className={
                    meanUpside > 0
                      ? "font-medium tabular-nums text-success"
                      : meanUpside < 0
                        ? "font-medium tabular-nums text-destructive"
                        : "font-medium tabular-nums"
                  }
                >
                  {meanUpside > 0 ? "+" : ""}
                  {meanUpside.toFixed(1)}%
                </span>
              </>
            )}
          </span>
        ) : (
          <span className="text-[9px] text-muted-foreground">{values.length} est.</span>
        )}
      </header>
      <div className="px-1.5 py-1">{children}</div>
    </section>
  );

  if (values.length < 3) {
    return card(
      <p className="py-8 text-center text-[10px] text-muted-foreground">
        Not enough fair-value estimates to plot a distribution.
      </p>,
    );
  }

  const priceMarker =
    currentPrice !== null && Number.isFinite(currentPrice) ? currentPrice : null;
  const extra = [
    ...(priceMarker !== null ? [priceMarker] : []),
    ...(valueArea ? [valueArea.low, valueArea.high, valueArea.mean] : []),
  ];
  const bins = buildBins(values, extra);
  const priceIdx = priceMarker !== null ? binIndexOf(bins, priceMarker) : null;

  // Which bins fall inside the value area — those are drawn solid, the trimmed
  // tails muted, so the central 70% reads at a glance.
  const inValueArea = (b: Bin): boolean =>
    valueArea !== null && b.end >= valueArea.low && b.start <= valueArea.high;
  const areaLoIdx = valueArea ? binIndexOf(bins, valueArea.low) : null;
  const areaHiIdx = valueArea ? binIndexOf(bins, valueArea.high) : null;
  const meanIdx = valueArea ? binIndexOf(bins, valueArea.mean) : null;

  return card(
    <div style={{ width: "100%", height: 160 }}>
      <ResponsiveContainer>
        <BarChart data={bins} margin={{ top: 10, right: 6, bottom: 0, left: 0 }}>
          <XAxis
            dataKey="idx"
            type="category"
            tick={{ fontSize: 8, fill: "hsl(var(--muted-foreground))" }}
            stroke="hsl(var(--border))"
            interval={0}
            tickFormatter={(idx: number) => formatAbbreviated(bins[idx].center)}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fontSize: 8, fill: "hsl(var(--muted-foreground))" }}
            stroke="hsl(var(--border))"
            width={18}
          />
          <Tooltip
            cursor={{ fill: "hsl(var(--accent) / 0.4)" }}
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              fontSize: 10,
            }}
            labelStyle={{ color: "hsl(var(--foreground))" }}
            itemStyle={{ color: "hsl(var(--foreground))" }}
            formatter={(value: number) => [`${value} est.`, "Estimates"]}
            labelFormatter={(idx: number) =>
              `${formatCurrency(bins[idx].start, currency)} – ${formatCurrency(
                bins[idx].end,
                currency,
              )}`
            }
          />
          {areaLoIdx !== null && areaHiIdx !== null && (
            <ReferenceArea
              x1={areaLoIdx}
              x2={areaHiIdx}
              fill="hsl(var(--primary))"
              fillOpacity={0.08}
              ifOverflow="extendDomain"
            />
          )}
          <Bar dataKey="count" radius={[1, 1, 0, 0]} isAnimationActive={false}>
            {bins.map((b) => (
              <Cell
                key={b.idx}
                fill={
                  inValueArea(b) ? "hsl(var(--primary))" : "hsl(var(--muted-foreground))"
                }
                fillOpacity={inValueArea(b) ? 1 : 0.35}
              />
            ))}
          </Bar>
          {meanIdx !== null && (
            <ReferenceLine
              x={meanIdx}
              stroke="hsl(var(--primary))"
              strokeWidth={1.5}
              label={{
                value: "VA mean",
                position: "top",
                fontSize: 8,
                fill: "hsl(var(--primary))",
              }}
            />
          )}
          {priceIdx !== null && (
            <ReferenceLine
              x={priceIdx}
              stroke="hsl(var(--destructive))"
              strokeWidth={1.25}
              strokeDasharray="3 2"
              label={{
                value: "Price",
                position: "top",
                fontSize: 8,
                fill: "hsl(var(--destructive))",
              }}
            />
          )}
        </BarChart>
      </ResponsiveContainer>
    </div>,
  );
}
