/**
 * Portfolio overview hook + types — powers the Home page (Task 24).
 *
 * The backend `/api/portfolio/overview` already aggregates stats and
 * pre-shapes per-stock rows from each stock's latest live snapshot,
 * so the Home page only needs to filter/sort and render.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { stocksKey } from "@/lib/stocks";

export interface SparklinePoint {
  created_at: string;
  general_grade: string | null;
}

export interface ScenarioFairValue {
  fair_value: number | null;
  upside_pct: number | null;
}

export interface PortfolioStockRow {
  symbol: string;
  currency: string;
  category: string | null;
  notes: string | null;
  last_updated: string | null;
  general_grade: string | null;
  sub_grades: Record<string, string | null>;
  average_fair_value: string | null;
  current_price: string | null;
  upside_pct: string | null;
  /** Per-scenario fair values from the latest fair-values job (null if none). */
  fair_values: Record<string, ScenarioFairValue> | null;
  sparkline: SparklinePoint[];
}

export interface PortfolioStats {
  total_stocks: number;
  average_general_grade: string | null;
  undervalued_count: number;
  overvalued_count: number;
}

export interface PortfolioOverview {
  stats: PortfolioStats;
  stocks: PortfolioStockRow[];
}

export const PORTFOLIO_QUERY_KEY = ["portfolio", "overview"] as const;

export function usePortfolioOverview() {
  return useQuery({
    queryKey: PORTFOLIO_QUERY_KEY,
    queryFn: () => api<PortfolioOverview>("/api/portfolio/overview"),
  });
}

/** Set (or clear, with null) a stock's category from the portfolio table. */
export function useSetCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ symbol, category }: { symbol: string; category: string | null }) =>
      api<unknown>(`/api/stocks/${encodeURIComponent(symbol)}`, {
        method: "PATCH",
        body: { category },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PORTFOLIO_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: stocksKey });
    },
  });
}

/** Delete a ticker and all its data. */
export function useDeleteTicker() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (symbol: string) =>
      api<void>(`/api/stocks/${encodeURIComponent(symbol)}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PORTFOLIO_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: stocksKey });
    },
  });
}
