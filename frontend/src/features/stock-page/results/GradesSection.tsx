/**
 * Grades section — runs the analysis automatically when the stock page opens
 * (no manual "Run valuation" step). Populates the shared analysis store, which
 * also drives the Growth section. Renders the sub-grade radar + cards.
 *
 * Grades depend only on the stock's financials, settings, and per-stock market
 * data (current price + beta) — not on the valuation target multiples — so the
 * auto-run just passes the saved current_price/beta and lets the backend fill
 * the rest from global defaults.
 */

import { useEffect } from "react";

import { CollapsibleSection } from "@/components/CollapsibleSection";
import { GradeChip } from "@/components/GradeChip";
import { type AnalysisResult, useAnalyze } from "@/lib/analysis";
import { METRIC_LABELS, SUB_GRADE_LABELS } from "@/lib/defaults";
import { useParameters } from "@/lib/parameters";
import { useNumberFormat } from "@/lib/settings";
import { useAnalysisResult } from "@/stores/analysis";

import { SubGradeRadar } from "./SubGradeRadar";

interface GradesSectionProps {
  symbol: string;
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

export function GradesSection({ symbol }: GradesSectionProps) {
  const parametersQuery = useParameters(symbol);
  const analyze = useAnalyze(symbol);
  const result = useAnalysisResult(symbol);

  const paramsReady = parametersQuery.isSuccess;
  const currentPrice = parametersQuery.data?.current_price ?? null;
  const beta = parametersQuery.data?.beta ?? null;
  const { mutate } = analyze;

  // Auto-run on open and whenever the saved market data changes.
  useEffect(() => {
    if (!paramsReady) return;
    mutate({ current_price: currentPrice, beta });
  }, [paramsReady, currentPrice, beta, symbol, mutate]);

  const generalScore = result?.grades.general ?? null;

  return (
    <CollapsibleSection
      title="Grades"
      trailing={
        result ? (
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
              General
            </span>
            {generalScore === null ? (
              <span className="text-[11px] text-muted-foreground">—</span>
            ) : (
              <GradeChip value={generalScore} size="md" />
            )}
          </div>
        ) : null
      }
    >
      {analyze.isPending && !result ? (
        <p className="text-[11px] text-muted-foreground">Calculating grades…</p>
      ) : analyze.isError && !result ? (
        <p className="text-[11px] text-destructive">
          Couldn't calculate grades. {(analyze.error as Error).message}
        </p>
      ) : result ? (
        <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          <div className="rounded-md border border-border bg-card p-1.5 text-[11px]">
            <header className="mb-1 flex items-center justify-between gap-2 border-b border-border/60 pb-1">
              <span className="truncate text-[11px] font-semibold">Profile</span>
            </header>
            <SubGradeRadar
              columns={[{ label: "Grades" }]}
              results={{ Grades: result }}
              height={150}
            />
          </div>
          {SUB_GRADE_ORDER.map((subGrade) => (
            <SubGradeCard key={subGrade} subGrade={subGrade} result={result} />
          ))}
        </div>
      ) : (
        <p className="text-[11px] text-muted-foreground">No grades yet.</p>
      )}
    </CollapsibleSection>
  );
}

function SubGradeCard({
  subGrade,
  result,
}: {
  subGrade: string;
  result: AnalysisResult;
}) {
  const formatNumber = useNumberFormat();
  const block = result.grades.sub_grades[subGrade];
  const entries = block ? Object.entries(block.breakdown) : [];

  return (
    <div className="rounded-md border border-border bg-card p-1.5 text-[11px]">
      <header className="mb-1 flex items-center justify-between gap-2 border-b border-border/60 pb-1">
        <span className="truncate text-[11px] font-semibold">
          {SUB_GRADE_LABELS[subGrade] ?? subGrade}
        </span>
        {block ? (
          <GradeChip value={block.score} size="sm" />
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </header>
      {entries.length === 0 ? (
        <p className="text-[10px] text-muted-foreground">No metrics scored.</p>
      ) : (
        <ul className="space-y-0.5">
          {entries.map(([metric, entry]) => (
            <li key={metric} className="flex items-center justify-between gap-1.5">
              <span
                className="truncate text-muted-foreground"
                title={METRIC_LABELS[metric] ?? metric}
              >
                {METRIC_LABELS[metric] ?? metric}
              </span>
              <div className="flex flex-shrink-0 items-center gap-1 tabular-nums">
                <span className="text-[10px] text-muted-foreground">
                  {entry.value === null
                    ? "—"
                    : formatNumber(entry.value, { decimalPlaces: 2 })}
                </span>
                <GradeChip value={entry.score} size="sm" />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
