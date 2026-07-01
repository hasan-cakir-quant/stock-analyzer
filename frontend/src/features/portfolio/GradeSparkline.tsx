/**
 * Tiny in-cell sparkline (FR-3.8.1.3).
 *
 * Plots up to ~10 recent General Grade points so the user can see a
 * trend at a glance. Designed to live inside a table cell — no axes,
 * no tooltip, fixed small dimensions.
 */

import { LineChart, Line, ResponsiveContainer, YAxis } from "recharts";

import type { SparklinePoint } from "@/lib/portfolio";

interface GradeSparklineProps {
  points: SparklinePoint[];
  width?: number;
  height?: number;
}

interface ChartPoint {
  index: number;
  grade: number | null;
}

export function GradeSparkline({
  points,
  width = 70,
  height = 22,
}: GradeSparklineProps) {
  const data: ChartPoint[] = points.map((p, i) => ({
    index: i,
    grade: p.general_grade === null ? null : Number(p.general_grade),
  }));

  const finitePoints = data.filter(
    (d) => d.grade !== null && Number.isFinite(d.grade),
  );

  if (finitePoints.length < 2) {
    return (
      <span className="text-[10px] text-muted-foreground">
        {finitePoints.length === 1 ? `${Math.round(finitePoints[0].grade!)}` : "—"}
      </span>
    );
  }

  // Pick a stroke colour from the trend so the eye reads direction without
  // hovering the row: rising → success, falling → destructive, flat → primary.
  const first = finitePoints[0].grade!;
  const last = finitePoints[finitePoints.length - 1].grade!;
  const stroke =
    last > first + 1
      ? "hsl(var(--success))"
      : last < first - 1
        ? "hsl(var(--destructive))"
        : "hsl(var(--primary))";

  return (
    <div style={{ width, height }} aria-label="General grade trend">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
          <YAxis hide domain={[0, 100]} />
          <Line
            type="monotone"
            dataKey="grade"
            stroke={stroke}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
