/**
 * Distribution of General Grade across the portfolio (FR-3.8.1).
 *
 * Histogram with 5 buckets matching the colour bands used everywhere
 * else: 0-39 / 40-59 / 60-79 / 80-100, plus an explicit "Incomplete"
 * bucket for stocks without a snapshot yet.
 */

import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { PortfolioStockRow } from "@/lib/portfolio";

interface GradeDistributionProps {
  stocks: PortfolioStockRow[];
}

interface Bucket {
  label: string;
  range: [number, number] | null; // null = Incomplete
  fill: string;
}

const BUCKETS: Bucket[] = [
  { label: "0–39", range: [0, 39], fill: "hsl(var(--destructive))" },
  { label: "40–59", range: [40, 59], fill: "rgb(251 146 60)" },
  { label: "60–79", range: [60, 79], fill: "hsl(var(--warning))" },
  { label: "80–100", range: [80, 100], fill: "hsl(var(--success))" },
  { label: "Incomplete", range: null, fill: "hsl(var(--muted-foreground))" },
];

export function GradeDistribution({ stocks }: GradeDistributionProps) {
  const counts = BUCKETS.map((b) => ({ ...b, count: 0 }));

  for (const s of stocks) {
    const raw = s.general_grade;
    const value = raw === null ? null : Number(raw);
    if (value === null || !Number.isFinite(value)) {
      counts[counts.length - 1].count += 1;
      continue;
    }
    const idx = counts.findIndex(
      (b) => b.range !== null && value >= b.range[0] && value <= b.range[1],
    );
    if (idx !== -1) counts[idx].count += 1;
  }

  const data = counts.map(({ label, count, fill }) => ({ label, count, fill }));
  const hasAny = data.some((d) => d.count > 0);

  return (
    <section className="rounded-md border border-border bg-card text-card-foreground shadow-sm">
      <header className="flex items-center justify-between border-b border-border px-2.5 py-1.5">
        <h2 className="text-xs font-medium">General grade distribution</h2>
        <span className="text-[10px] text-muted-foreground">
          {stocks.length} stocks
        </span>
      </header>
      <div className="px-2 py-1.5">
        {!hasAny ? (
          <p className="py-4 text-center text-[11px] text-muted-foreground">
            Save snapshots on at least one stock to see grade distribution.
          </p>
        ) : (
          <div style={{ width: "100%", height: 140 }}>
            <ResponsiveContainer>
              <BarChart
                data={data}
                margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
              >
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                  stroke="hsl(var(--border))"
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                  stroke="hsl(var(--border))"
                  width={24}
                />
                <Tooltip
                  cursor={{ fill: "hsl(var(--accent) / 0.4)" }}
                  contentStyle={{
                    backgroundColor: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    fontSize: 11,
                  }}
                  labelStyle={{ color: "hsl(var(--foreground))" }}
                  formatter={(value: number) => [`${value} stocks`, ""]}
                />
                <Bar dataKey="count" radius={[2, 2, 0, 0]}>
                  {data.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </section>
  );
}
