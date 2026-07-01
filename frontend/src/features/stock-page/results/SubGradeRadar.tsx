/**
 * Sub-grade radar — overlays each comparison column as one polygon on a
 * 7-axis chart (Profitability / Valuation / Financial Strength / Growth /
 * Efficiency / Safety / Dividend). Lets the user eyeball each template's
 * profile shape vs. the others without scanning a numeric table.
 */

import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

import type { AnalysisResult } from "@/lib/analysis";
import { SUB_GRADE_LABELS } from "@/lib/defaults";

const SUB_GRADE_ORDER = [
  "profitability",
  "valuation",
  "financial_strength",
  "growth",
  "efficiency",
  "safety",
  "dividend",
] as const;

/** Distinct, theme-agnostic palette — cycled when columns > palette length. */
export const COLUMN_COLORS = [
  "hsl(217, 91%, 60%)", // blue
  "hsl(142, 71%, 45%)", // green
  "hsl(38, 92%, 50%)", // amber
  "hsl(0, 84%, 60%)", // red
  "hsl(280, 70%, 60%)", // purple
  "hsl(180, 70%, 45%)", // teal
];

export function columnColor(index: number): string {
  return COLUMN_COLORS[index % COLUMN_COLORS.length];
}

interface SubGradeRadarProps {
  columns: { label: string }[];
  results: Record<string, AnalysisResult>;
  height?: number;
}

export function SubGradeRadar({ columns, results, height = 260 }: SubGradeRadarProps) {
  // Recharts wants one row per axis, with one numeric key per series.
  // Keys are the column labels, so columns with identical labels would
  // collide — `columns` is built from "Current" + unique template names,
  // so collisions don't happen in practice.
  const data = SUB_GRADE_ORDER.map((name) => {
    const row: Record<string, string | number | null> = {
      subGrade: SUB_GRADE_LABELS[name] ?? name,
    };
    for (const col of columns) {
      const score = results[col.label]?.grades.sub_grades[name]?.score;
      row[col.label] = score ?? null;
    }
    return row;
  });

  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer>
        <RadarChart data={data} margin={{ top: 8, right: 24, bottom: 8, left: 24 }}>
          <PolarGrid stroke="hsl(var(--border))" />
          <PolarAngleAxis
            dataKey="subGrade"
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 100]}
            tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }}
            stroke="hsl(var(--border))"
          />
          {columns.map((col, i) => (
            <Radar
              key={col.label}
              name={col.label}
              dataKey={col.label}
              stroke={columnColor(i)}
              fill={columnColor(i)}
              fillOpacity={0.18}
              strokeWidth={1.5}
              isAnimationActive={false}
            />
          ))}
          <Tooltip
            contentStyle={{
              fontSize: 11,
              padding: "4px 8px",
              background: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: 4,
            }}
            labelStyle={{ color: "hsl(var(--foreground))" }}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
