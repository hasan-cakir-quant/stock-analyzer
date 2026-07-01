import { ChevronDown, Info } from "lucide-react";
import { useState } from "react";

import { CollapsibleSection } from "@/components/CollapsibleSection";
import { GradeChip } from "@/components/GradeChip";
import { HoverPopover } from "@/components/HoverPopover";
import type { GradesBlock } from "@/lib/analysis";
import { METRIC_LABELS, SUB_GRADE_LABELS } from "@/lib/defaults";
import {
  getMetricExplainer,
  type InputFormat,
  type MetricExplainer,
} from "@/lib/explainers";
import {
  useNumberFormat,
  usePercentFormat,
  useSettings,
} from "@/lib/settings";
import { cn } from "@/lib/utils";

interface GradesCardProps {
  grades: GradesBlock;
}

const SUB_GRADE_ORDER = [
  "profitability",
  "valuation",
  "financial_strength",
  "growth",
  "efficiency",
  "safety",
  "dividend",
] as const;

export function GradesCard({ grades }: GradesCardProps) {
  // One sub-grade can be expanded at a time so the breakdown table
  // doesn't push every other section off-screen.
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <CollapsibleSection
      title="Grades"
      trailing={<GradeChip value={grades.general} label="General" size="lg" />}
    >
      <div className="grid gap-1.5 sm:grid-cols-2 2xl:grid-cols-3">
        {SUB_GRADE_ORDER.map((name) => {
          const sg = grades.sub_grades[name];
          if (!sg) return null;
          const isExpanded = expanded === name;
          return (
            <SubGradeButton
              key={name}
              name={name}
              score={sg.score}
              metricsUsed={sg.metrics_used}
              metricsTotal={sg.metrics_total}
              expanded={isExpanded}
              onToggle={() => setExpanded(isExpanded ? null : name)}
            />
          );
        })}
      </div>

      {expanded && grades.sub_grades[expanded] && (
        <BreakdownTable
          name={expanded}
          breakdown={grades.sub_grades[expanded].breakdown}
        />
      )}
    </CollapsibleSection>
  );
}

interface SubGradeButtonProps {
  name: string;
  score: number | null;
  metricsUsed: number;
  metricsTotal: number;
  expanded: boolean;
  onToggle: () => void;
}

function SubGradeButton({
  name,
  score,
  metricsUsed,
  metricsTotal,
  expanded,
  onToggle,
}: SubGradeButtonProps) {
  const partial = metricsUsed > 0 && metricsUsed < metricsTotal;
  return (
    <button
      type="button"
      onClick={onToggle}
      className={cn(
        "flex w-full items-center justify-between gap-2 rounded-md border border-border bg-card px-2 py-1 text-left text-[11px] transition-colors hover:bg-accent",
        expanded && "border-primary/40 bg-accent",
      )}
    >
      <div className="flex flex-col">
        <span className="font-medium">{SUB_GRADE_LABELS[name] ?? name}</span>
        {partial && (
          <span className="text-[9px] text-muted-foreground">
            based on {metricsUsed} of {metricsTotal} metrics
          </span>
        )}
      </div>
      <div className="flex items-center gap-1">
        <GradeChip value={score} size="sm" />
        <ChevronDown
          className={cn(
            "h-3 w-3 text-muted-foreground transition-transform",
            expanded ? "rotate-180" : "",
          )}
        />
      </div>
    </button>
  );
}

interface BreakdownTableProps {
  name: string;
  breakdown: Record<string, { value: number | null; score: number | null }>;
}

function BreakdownTable({ name, breakdown }: BreakdownTableProps) {
  const formatNumber = useNumberFormat();
  const entries = Object.entries(breakdown);
  const settings = useSettings();
  const thresholds = (settings.data?.grade_thresholds ?? {}) as Record<string, ThresholdTable>;
  const subGradeWeights = (settings.data?.sub_grade_weights?.[name] ?? {}) as Record<
    string,
    number | string
  >;

  return (
    <div className="mt-2 rounded-md border border-border bg-background p-1.5 text-[11px]">
      <div className="mb-1 px-1 text-[10px] uppercase tracking-wide text-muted-foreground">
        {SUB_GRADE_LABELS[name] ?? name} breakdown
      </div>
      <table className="w-full">
        <thead>
          <tr className="border-b border-border/60 text-[9px] uppercase tracking-wide text-muted-foreground">
            <th className="px-1 py-0.5 text-left font-medium">Metric</th>
            <th className="px-1 py-0.5 text-right font-medium">Raw value</th>
            <th className="px-1 py-0.5 text-right font-medium">Score</th>
            <th className="w-4 px-0.5 py-0.5"></th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([metric, { value, score }]) => {
            const explainer = getMetricExplainer(metric);
            const threshold = thresholds[metric];
            const weight = subGradeWeights[metric];
            return (
              <tr key={metric} className="border-b border-border/30 last:border-b-0">
                <td className="px-1 py-0.5 text-foreground">
                  {METRIC_LABELS[metric] ?? metric}
                </td>
                <td className="px-1 py-0.5 text-right tabular-nums text-muted-foreground">
                  {value === null ? "—" : formatNumber(value, { decimalPlaces: 4 })}
                </td>
                <td className="px-1 py-0.5 text-right">
                  <GradeChip value={score} size="sm" />
                </td>
                <td className="px-0.5 py-0.5 text-right">
                  {explainer && (
                    <HoverPopover
                      placement="top-right"
                      content={
                        <MetricExplainerPanel
                          metric={metric}
                          explainer={explainer}
                          value={value}
                          score={score}
                          threshold={threshold}
                          weight={weight}
                        />
                      }
                    >
                      <button
                        type="button"
                        aria-label={`Show how ${METRIC_LABELS[metric] ?? metric} is computed`}
                        className="rounded p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                      >
                        <Info className="h-3 w-3" />
                      </button>
                    </HoverPopover>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------

interface ThresholdTable {
  direction?: "higher_better" | "lower_better";
  ranges?: Array<[number | null, number]>;
}

interface MetricExplainerPanelProps {
  metric: string;
  explainer: MetricExplainer;
  value: number | null;
  score: number | null;
  threshold: ThresholdTable | undefined;
  weight: number | string | undefined;
}

function MetricExplainerPanel({
  metric,
  explainer,
  value,
  score,
  threshold,
  weight,
}: MetricExplainerPanelProps) {
  const formatNumber = useNumberFormat();
  const formatPercent = usePercentFormat();

  function formatValue(format: InputFormat, raw: number | null): string {
    if (raw === null) return "—";
    switch (format) {
      case "percent":
        return formatPercent(raw, { fromFraction: true, decimalPlaces: 2 });
      case "percent_pct":
        return `${formatNumber(raw, { decimalPlaces: 2 })}%`;
      case "integer":
        return formatNumber(raw, { decimalPlaces: 0 });
      case "ratio":
        return `${formatNumber(raw, { decimalPlaces: 2 })}×`;
      default:
        return formatNumber(raw, { decimalPlaces: 2 });
    }
  }

  function formatBoundary(boundary: number | null): string {
    if (boundary === null) return "otherwise";
    return formatValue(explainer.valueFormat, boundary);
  }

  // Highlight the band that produced the current score.
  const ranges = threshold?.ranges ?? [];
  const direction = threshold?.direction;
  const matchedIndex = (() => {
    if (value === null || direction === undefined) return -1;
    for (let i = 0; i < ranges.length; i++) {
      const [boundary] = ranges[i];
      if (boundary === null) return i;
      if (direction === "higher_better" && value >= boundary) return i;
      if (direction === "lower_better" && value <= boundary) return i;
    }
    return -1;
  })();

  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs font-semibold">
          {METRIC_LABELS[metric] ?? metric}
        </span>
        {score !== null && (
          <span className="text-xs font-semibold tabular-nums">{score}</span>
        )}
      </div>
      <div className="rounded bg-muted/40 px-1.5 py-1 font-mono text-[10px] leading-snug">
        {explainer.formula}
      </div>
      <p className="text-[10px] leading-snug text-muted-foreground">
        {explainer.description}
      </p>

      <div className="flex items-baseline justify-between gap-2 border-t border-border pt-1">
        <span className="text-muted-foreground">Raw value</span>
        <span className="font-medium tabular-nums">
          {formatValue(explainer.valueFormat, value)}
        </span>
      </div>
      {weight !== undefined && (
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-muted-foreground">Weight in sub-grade</span>
          <span className="font-medium tabular-nums">
            {formatNumber(typeof weight === "string" ? Number(weight) : weight, {
              decimalPlaces: 2,
            })}
          </span>
        </div>
      )}

      {ranges.length > 0 && (
        <div className="border-t border-border pt-1">
          <div className="mb-0.5 text-[9px] uppercase tracking-wide text-muted-foreground">
            Scoring bands · {direction === "lower_better" ? "lower is better" : "higher is better"}
          </div>
          <div className="space-y-0.5">
            {ranges.map(([boundary, bandScore], i) => (
              <div
                key={i}
                className={cn(
                  "flex items-baseline justify-between gap-2 rounded px-1 py-0.5 tabular-nums",
                  i === matchedIndex && "bg-accent text-foreground",
                )}
              >
                <span className="text-muted-foreground">
                  {direction === "higher_better" && boundary !== null && "≥ "}
                  {direction === "lower_better" && boundary !== null && "≤ "}
                  {formatBoundary(boundary)}
                </span>
                <span className="font-medium">{bandScore}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
