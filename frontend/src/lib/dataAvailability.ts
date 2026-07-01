/**
 * Data-availability overview + per-stock incremental refresh.
 *
 * `useDataAvailability` lists every stock's coverage (quarters stored, latest
 * quarter, whether the latest quarter has a closing price, current price/beta).
 * `useRefreshStock` tops a stock up — it adds only quarters newer than the
 * latest stored one, fetches their closing prices, and refreshes current
 * price/beta — then invalidates the affected caches.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { financialsKey } from "@/lib/financials";
import type { JobType } from "@/lib/jobs";
import { parametersKey } from "@/lib/parameters";
import { PORTFOLIO_QUERY_KEY } from "@/lib/portfolio";
import { stockKey, stocksKey } from "@/lib/stocks";

export interface DataAvailabilityItem {
  symbol: string;
  currency: string;
  category: string | null;
  is_financial: boolean;
  quarters_count: number;
  latest_quarter: string | null;
  latest_quarter_end_date: string | null;
  closing_price_count: number;
  latest_quarter_has_close: boolean;
  has_current_price: boolean;
  current_price: string | null;
  beta: string | null;
  financials_updated_at: string | null;
  price_updated_at: string | null;
  fair_values_at: string | null;
  grades_at: string | null;
}

export interface RefreshStep {
  ok: boolean;
  detail?: string;
  value?: string | null;
  written?: number;
  source?: string;
  new_periods?: string[];
  latest_before?: string | null;
  latest_after?: string | null;
  current_price?: string | null;
  beta?: string | null;
}

export interface RefreshResult {
  symbol: string;
  source: string;
  steps: {
    cik?: RefreshStep;
    financials?: RefreshStep;
    closing_prices?: RefreshStep;
    market_data?: RefreshStep;
  };
}

export const dataAvailabilityKey = ["data-availability"] as const;

export function useDataAvailability() {
  return useQuery({
    queryKey: dataAvailabilityKey,
    queryFn: () => api<DataAvailabilityItem[]>("/api/data/availability"),
  });
}

export interface SeedSp500Result {
  total: number;
  created: number;
  skipped: number;
  created_symbols: string[];
}

/** Create empty USD stock shells for every current S&P 500 constituent
 * (fetched from Wikipedia). No financial/price data is pulled. */
export function useSeedSp500() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      api<SeedSp500Result>("/api/stocks/seed-sp500", { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: dataAvailabilityKey });
      queryClient.invalidateQueries({ queryKey: stocksKey });
      queryClient.invalidateQueries({ queryKey: PORTFOLIO_QUERY_KEY });
    },
  });
}

export interface StockJobResult {
  symbol: string;
  job_type: JobType;
  ok: boolean;
}

/** Run a single job for one stock (synchronous on the server). Pass
 * `{ symbol, jobType }` to `mutateAsync`. */
export function useRunStockJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ symbol, jobType }: { symbol: string; jobType: JobType }) =>
      api<StockJobResult>(
        `/api/stocks/${encodeURIComponent(symbol)}/run/${jobType}`,
        { method: "POST" },
      ),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: dataAvailabilityKey });
      queryClient.invalidateQueries({ queryKey: PORTFOLIO_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: financialsKey(result.symbol) });
      queryClient.invalidateQueries({ queryKey: parametersKey(result.symbol) });
      queryClient.invalidateQueries({ queryKey: stockKey(result.symbol) });
    },
  });
}

/** Refresh any stock by symbol — pass the symbol to `mutate`/`mutateAsync`. */
export function useRefreshStock() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (symbol: string) =>
      api<RefreshResult>(`/api/stocks/${encodeURIComponent(symbol)}/refresh`, {
        method: "POST",
      }),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: dataAvailabilityKey });
      queryClient.invalidateQueries({ queryKey: financialsKey(result.symbol) });
      queryClient.invalidateQueries({ queryKey: parametersKey(result.symbol) });
      queryClient.invalidateQueries({ queryKey: stockKey(result.symbol) });
      queryClient.invalidateQueries({ queryKey: ["snapshots"] });
    },
  });
}
