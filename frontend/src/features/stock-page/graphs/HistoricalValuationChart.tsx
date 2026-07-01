/**
 * Historical valuation chart — implied fair price per quarter vs. actual price.
 *
 * For each quarter T we take the trailing moving average (MA4 / MA8 / MA12) of
 * the stock's *own realized* multiple (P/E, EV/EBITDA, EV/EBIT) as the target
 * multiple, then apply it to T's TTM fundamentals to get an implied fair price
 * per share:
 *
 *   P/E based      : fairPx = MAk(P/E) × TTM EPS
 *   EV/EBITDA based: fairPx = (MAk(EV/EBITDA) × TTM EBITDA − net debt) / shares
 *   EV/EBIT based  : fairPx = (MAk(EV/EBIT)  × TTM EBIT   − net debt) / shares
 *
 * All nine lines are plotted against the quarter-end closing price, so you can
 * see when the stock traded rich or cheap versus its own multiple history.
 * Click a legend entry to toggle that line.
 */

import { Maximize2 } from "lucide-react";
import { useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Modal } from "@/components/Modal";
import { useFinancials } from "@/lib/financials";
import { useParameters } from "@/lib/parameters";
import { useNumberFormat } from "@/lib/settings";

import { clampToWindow, useMaxQuarters } from "./graphsFilter";
import { fillIsolatedGaps, movingAverageAt, trailingTtm } from "./ttm";

interface HistoricalValuationChartProps {
  symbol: string;
  isFinancial?: boolean;
}

const WINDOWS = [4, 8, 12] as const;

// One color per method; dash pattern per MA window (dotted=4, dashed=8, solid=12).
const METHODS = [
  { key: "pe", label: "P/E", color: "hsl(217, 91%, 60%)" },
  { key: "pb", label: "P/B", color: "hsl(280, 65%, 60%)" },
  { key: "evEbitda", label: "EV/EBITDA", color: "hsl(142, 71%, 45%)" },
  { key: "evEbit", label: "EV/EBIT", color: "hsl(38, 92%, 50%)" },
  { key: "evFcf", label: "EV/FCF", color: "hsl(180, 65%, 42%)" },
] as const;

// EV-based methods don't apply to financials (deposits aren't debt).
const FINANCIAL_METHODS = new Set(["pe", "pb"]);

const DASH: Record<number, string | undefined> = { 4: "2 2", 8: "5 3", 12: undefined };

interface SeriesDef {
  key: string;
  name: string;
  color: string;
  dash?: string;
  width: number;
}

function num(v: string | null): number | null {
  return v === null ? null : Number(v);
}

export function HistoricalValuationChart({
  symbol,
  isFinancial = false,
}: HistoricalValuationChartProps) {
  const financialsQuery = useFinancials(symbol);
  const parametersQuery = useParameters(symbol);
  const formatNumber = useNumberFormat();
  const maxQuarters = useMaxQuarters();
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [expanded, setExpanded] = useState(false);

  // Latest fetched price (from Market Data / Fetch all) — drawn as a red level.
  const currentPrice =
    parametersQuery.data?.current_price != null
      ? Number(parametersQuery.data.current_price)
      : null;
  const hasCurrentPrice = currentPrice !== null && Number.isFinite(currentPrice);

  const methods = METHODS.filter((m) => !isFinancial || FINANCIAL_METHODS.has(m.key));
  const series: SeriesDef[] = [
    ...methods.flatMap((m) =>
      WINDOWS.map((w) => ({
        key: `${m.key}_ma${w}`,
        name: `${m.label} MA${w}`,
        color: m.color,
        dash: DASH[w],
        width: 1.25,
      })),
    ),
    { key: "price", name: "Price", color: "hsl(var(--foreground))", width: 2 },
  ];

  const rows = (financialsQuery.data ?? [])
    .slice()
    .sort((a, b) => a.period.localeCompare(b.period));

  const filledEps = fillIsolatedGaps(rows.map((r) => num(r.eps_diluted)));
  const filledEbitda = fillIsolatedGaps(rows.map((r) => num(r.ebitda)));
  const filledEbit = fillIsolatedGaps(rows.map((r) => num(r.operating_income)));
  const filledFcf = fillIsolatedGaps(rows.map((r) => num(r.free_cash_flow)));

  // Per-quarter realized multiples (price-based), used to derive the MA targets.
  const ev: (number | null)[] = rows.map((r) => {
    const price = num(r.closing_price);
    const shares = num(r.shares_outstanding_diluted);
    if (price === null || shares === null) return null;
    const netDebt =
      (num(r.long_term_debt) ?? 0) + (num(r.short_term_debt) ?? 0) - (num(r.cash_and_equivalents) ?? 0);
    return price * shares + netDebt;
  });
  const netDebtSeries = rows.map(
    (r) => (num(r.long_term_debt) ?? 0) + (num(r.short_term_debt) ?? 0) - (num(r.cash_and_equivalents) ?? 0),
  );

  // Book value per share per quarter, for the P/B line.
  const bvps: (number | null)[] = rows.map((r) => {
    const equity = num(r.total_equity);
    const shares = num(r.shares_outstanding_diluted);
    return equity !== null && shares !== null && shares > 0 ? equity / shares : null;
  });

  const realizedPe = rows.map((r, i) => {
    const price = num(r.closing_price);
    const ttmEps = trailingTtm(filledEps, i);
    return price !== null && ttmEps !== null && ttmEps > 0 ? price / ttmEps : null;
  });
  const realizedPb = rows.map((r, i) => {
    const price = num(r.closing_price);
    return price !== null && bvps[i] !== null && (bvps[i] as number) > 0
      ? price / (bvps[i] as number)
      : null;
  });
  // Guard negative EV (cash > market cap) so the realized multiple stays sane.
  const realizedEvEbitda = rows.map((_, i) => {
    const ttm = trailingTtm(filledEbitda, i);
    return ev[i] !== null && (ev[i] as number) > 0 && ttm !== null && ttm > 0
      ? (ev[i] as number) / ttm
      : null;
  });
  const realizedEvEbit = rows.map((_, i) => {
    const ttm = trailingTtm(filledEbit, i);
    return ev[i] !== null && (ev[i] as number) > 0 && ttm !== null && ttm > 0
      ? (ev[i] as number) / ttm
      : null;
  });
  const realizedEvFcf = rows.map((_, i) => {
    const ttm = trailingTtm(filledFcf, i);
    return ev[i] !== null && (ev[i] as number) > 0 && ttm !== null && ttm > 0
      ? (ev[i] as number) / ttm
      : null;
  });

  const data = rows.map((r, i) => {
    const shares = num(r.shares_outstanding_diluted);
    const ttmEps = trailingTtm(filledEps, i);
    const ttmEbitda = trailingTtm(filledEbitda, i);
    const ttmEbit = trailingTtm(filledEbit, i);
    const ttmFcf = trailingTtm(filledFcf, i);
    const netDebt = netDebtSeries[i];

    const point: Record<string, number | string | null> = {
      period: r.period,
      price: num(r.closing_price),
    };

    for (const w of WINDOWS) {
      const maPe = movingAverageAt(realizedPe, i, w);
      point[`pe_ma${w}`] = maPe !== null && ttmEps !== null ? maPe * ttmEps : null;

      const maPb = movingAverageAt(realizedPb, i, w);
      point[`pb_ma${w}`] = maPb !== null && bvps[i] !== null ? maPb * (bvps[i] as number) : null;

      const maEvEbitda = movingAverageAt(realizedEvEbitda, i, w);
      point[`evEbitda_ma${w}`] =
        maEvEbitda !== null && ttmEbitda !== null && shares !== null && shares > 0
          ? (maEvEbitda * ttmEbitda - netDebt) / shares
          : null;

      const maEvEbit = movingAverageAt(realizedEvEbit, i, w);
      point[`evEbit_ma${w}`] =
        maEvEbit !== null && ttmEbit !== null && shares !== null && shares > 0
          ? (maEvEbit * ttmEbit - netDebt) / shares
          : null;

      const maEvFcf = movingAverageAt(realizedEvFcf, i, w);
      point[`evFcf_ma${w}`] =
        maEvFcf !== null && ttmFcf !== null && shares !== null && shares > 0
          ? (maEvFcf * ttmFcf - netDebt) / shares
          : null;
    }

    return point;
  });

  // All MA/TTM math above runs over full history; trim to the selected window
  // for display so the moving-average lines stay correct at the left edge.
  const visible = clampToWindow(data, maxQuarters);

  const hasAny = visible.some((d) =>
    series.some((s) => typeof d[s.key] === "number" && Number.isFinite(d[s.key] as number)),
  );

  function toggle(key: string) {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function renderChart(height: number, big: boolean) {
    if (financialsQuery.isLoading) {
      return <p className="py-6 text-center text-[10px] text-muted-foreground">Loading…</p>;
    }
    if (!hasAny) {
      return (
        <p className="py-6 text-center text-[10px] text-muted-foreground">
          Not enough history — needs prices and trailing fundamentals.
        </p>
      );
    }
    const fontSize = big ? 11 : 9;
    return (
      <div style={{ width: "100%", height }}>
        <ResponsiveContainer>
          <LineChart data={visible} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="hsl(var(--border))" strokeOpacity={0.4} vertical={false} />
            <XAxis
              dataKey="period"
              tick={{ fontSize, fill: "hsl(var(--muted-foreground))" }}
              stroke="hsl(var(--border))"
              interval="preserveStartEnd"
              minTickGap={big ? 32 : 20}
            />
            <YAxis
              tick={{ fontSize, fill: "hsl(var(--muted-foreground))" }}
              stroke="hsl(var(--border))"
              width={big ? 52 : 40}
              tickFormatter={(v: number) => formatNumber(v, { decimalPlaces: 0 })}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "hsl(var(--card))",
                border: "1px solid hsl(var(--border))",
                fontSize: big ? 12 : 10,
              }}
              labelStyle={{ color: "hsl(var(--foreground))" }}
              itemStyle={{ color: "hsl(var(--foreground))" }}
              formatter={(value: number, name: string) => [
                formatNumber(value, { decimalPlaces: 2 }),
                name,
              ]}
            />
            <Legend
              wrapperStyle={{ fontSize: big ? 11 : 9, cursor: "pointer" }}
              onClick={(e) => toggle(String(e.dataKey))}
            />
            {series.map((s) => (
              <Line
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.name}
                stroke={s.color}
                strokeWidth={big ? s.width + 0.5 : s.width}
                strokeDasharray={s.dash}
                dot={false}
                isAnimationActive={false}
                connectNulls
                hide={hidden.has(s.key)}
              />
            ))}
            {hasCurrentPrice && (
              <ReferenceLine
                y={currentPrice as number}
                stroke="hsl(0, 84%, 60%)"
                strokeWidth={1.5}
                ifOverflow="extendDomain"
                label={{
                  value: `Current ${formatNumber(currentPrice, { decimalPlaces: 2 })}`,
                  position: "insideTopRight",
                  fill: "hsl(0, 84%, 60%)",
                  fontSize: big ? 11 : 9,
                }}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  return (
    <>
      <section className="rounded-md border border-border bg-card text-card-foreground shadow-sm">
        <header className="flex items-center justify-between border-b border-border px-2 py-1">
          <h3 className="truncate text-[11px] font-medium">
            Historical fair value vs price — multiple MAs
          </h3>
          <div className="flex items-center gap-1.5">
            <span className="text-[9px] text-muted-foreground">{visible.length}q</span>
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
        <div className="px-1.5 py-1">{renderChart(340, false)}</div>
      </section>

      <Modal
        open={expanded}
        onClose={() => setExpanded(false)}
        className="max-w-5xl"
        title={
          <span className="text-sm font-semibold">
            Historical fair value vs price — multiple MAs
          </span>
        }
      >
        {renderChart(560, true)}
      </Modal>
    </>
  );
}
