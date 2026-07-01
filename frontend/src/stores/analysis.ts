/**
 * Per-symbol latest Run Full Analysis result.
 *
 * The server analyze call is intentionally ephemeral (no persistence by
 * design — Task 12's snapshot endpoint is the path that freezes things),
 * so we keep the most recent result here so the Stock page's Results
 * Dashboard / Charts (Tasks 21/22) can read it across re-renders without
 * re-running the computation.
 */

import { create } from "zustand";

import type { AnalysisResult } from "@/lib/analysis";

interface AnalysisStore {
  results: Record<string, AnalysisResult>;
  setResult: (symbol: string, result: AnalysisResult) => void;
  clearResult: (symbol: string) => void;
}

export const useAnalysisStore = create<AnalysisStore>((set) => ({
  results: {},
  setResult: (symbol, result) =>
    set((state) => ({
      results: { ...state.results, [symbol.toUpperCase()]: result },
    })),
  clearResult: (symbol) =>
    set((state) => {
      const key = symbol.toUpperCase();
      if (!(key in state.results)) return state;
      const { [key]: _omit, ...rest } = state.results;
      return { results: rest };
    }),
}));

/** Selector hook — returns the latest result for one symbol (or undefined). */
export function useAnalysisResult(symbol: string | undefined): AnalysisResult | undefined {
  return useAnalysisStore((state) =>
    symbol ? state.results[symbol.toUpperCase()] : undefined,
  );
}
