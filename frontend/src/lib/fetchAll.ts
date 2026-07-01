/**
 * One-shot data fetch — CIK, financials, closing prices, current price & beta
 * in a single call. Fundamentals come from SEC EDGAR; prices from yfinance.
 * Each step is best-effort; the response reports per-step status.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { financialsKey } from "@/lib/financials";
import { parametersKey } from "@/lib/parameters";
import { stockKey } from "@/lib/stocks";

export interface FetchAllStep {
  ok: boolean;
  detail?: string;
  value?: string | null;
  written?: number;
  source?: string;
  current_price?: string | null;
  beta?: string | null;
}

export interface FetchAllResult {
  symbol: string;
  source: string;
  steps: {
    cik?: FetchAllStep;
    financials?: FetchAllStep;
    closing_prices?: FetchAllStep;
    market_data?: FetchAllStep;
  };
}

export function useFetchAll(symbol: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      api<FetchAllResult>(`/api/stocks/${encodeURIComponent(symbol)}/fetch-all`, {
        method: "POST",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: financialsKey(symbol) });
      queryClient.invalidateQueries({ queryKey: parametersKey(symbol) });
      queryClient.invalidateQueries({ queryKey: stockKey(symbol) });
      queryClient.invalidateQueries({ queryKey: ["snapshots"] });
    },
  });
}
