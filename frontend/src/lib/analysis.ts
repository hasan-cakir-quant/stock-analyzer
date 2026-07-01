/**
 * Run-Full-Analysis hook + analysis result typing.
 *
 * The result mirrors the JSON returned by `POST /api/stocks/{symbol}/analyze`
 * — valuations + grades + growth all in one payload. We keep the latest
 * result per symbol in a Zustand store so the Stock page's Results
 * Dashboard (Task 21) can read it without coupling to TanStack Query.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Snapshot } from "@/lib/snapshots";
import { useAnalysisStore } from "@/stores/analysis";

/**
 * Body for `POST /analyze` and snapshot creation. Per-stock market data
 * (`current_price`, `beta`) plus the transient target multiples typed into
 * the Valuations panel. Omitted targets fall back to the global defaults.
 */
export interface ValuationRunInput {
  current_price?: string | null;
  beta?: string | null;
  target_pe?: string | null;
  target_pb?: string | null;
  target_ev_ebitda?: string | null;
  target_ev_ebit?: string | null;
  target_ev_fcf?: string | null;
}

export interface ValuationStepDetail {
  label: string;
  value: number | null;
  format: string;
}

export interface ValuationStep {
  label: string;
  value: number | null;
  formula: string | null;
  /** Hint for the UI: "currency" | "percent" | "percent_pct" | "ratio" | "integer" | "number". */
  format: string;
  /** Optional indented sub-rows — used to expand a TTM into the four quarters that compose it. */
  details: ValuationStepDetail[] | null;
}

export interface ValuationModelResult {
  fair_value: number | null;
  computable: boolean;
  reason: string | null;
  inputs: Record<string, number | null>;
  steps: ValuationStep[];
}

export interface ValuationSummary {
  average: number | null;
  median: number | null;
  current_price: number | null;
  upside_pct: number | null;
}

export interface ValuationsBlock {
  models: Record<string, ValuationModelResult>;
  summary: ValuationSummary;
}

export interface SubGradeBreakdownEntry {
  value: number | null;
  score: number | null;
}

export interface SubGradeBlock {
  score: number | null;
  metrics_used: number;
  metrics_total: number;
  breakdown: Record<string, SubGradeBreakdownEntry>;
}

export interface GradesBlock {
  general: number | null;
  sub_grades: Record<string, SubGradeBlock>;
}

export interface GrowthBlock {
  horizons: string[]; // e.g. ["1Y","3Y","5Y","10Y"]
  metrics: Record<string, Record<string, number | null>>;
}

export interface AnalysisResult {
  symbol: string;
  current_price: number | null;
  valuations: ValuationsBlock;
  grades: GradesBlock;
  growth: GrowthBlock;
}

export function useAnalyze(symbol: string) {
  const setResult = useAnalysisStore((state) => state.setResult);
  return useMutation({
    mutationFn: (parameters: ValuationRunInput) =>
      api<AnalysisResult>(
        `/api/stocks/${encodeURIComponent(symbol)}/analyze`,
        { method: "POST", body: parameters },
      ),
    onSuccess: (result) => setResult(symbol, result),
  });
}

// ---------------------------------------------------------------------------
// Save Snapshot
// ---------------------------------------------------------------------------

export interface CreateSnapshotPayload {
  parameters?: ValuationRunInput;
  note?: string | null;
  /** MA-based valuation matrix frozen with the snapshot (computed client-side). */
  ma_valuations?: Record<string, unknown>;
}

const snapshotsKey = (symbol: string) =>
  ["snapshots", symbol.toUpperCase()] as const;

export function useCreateSnapshot(symbol: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateSnapshotPayload) =>
      api<Snapshot>(
        `/api/stocks/${encodeURIComponent(symbol)}/snapshots`,
        { method: "POST", body: payload },
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: snapshotsKey(symbol) });
      queryClient.invalidateQueries({ queryKey: ["snapshots"] });
    },
  });
}
