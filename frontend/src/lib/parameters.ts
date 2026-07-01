/** Per-stock Parameter Panel state — last-used values that drive analysis. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";

export interface MarketData {
  symbol: string;
  current_price: string | null;
  beta: string | null;
  source: string;
}

export function useFetchMarketData(symbol: string) {
  return useMutation({
    mutationFn: () =>
      api<MarketData>(
        `/api/stocks/${encodeURIComponent(symbol)}/market-data`,
      ),
  });
}

/**
 * Per-stock market data persisted in the Parameter Panel. Server returns
 * Decimals as strings; we keep them as strings throughout the UI to preserve
 * precision and round-trip cleanly through `<input type="number">` editing.
 *
 * Valuation target multiples (Target P/E, Target EV/EBITDA) are NOT stored
 * here — they're transient run-time inputs entered in the Valuations panel.
 */
export interface ParameterValues {
  current_price: string | null;
  beta: string | null;
}

export type ParameterField = keyof ParameterValues;

/** Effective Parameter Panel state — what the GET endpoint returns. */
export interface ParameterRead extends ParameterValues {
  stock_id: string;
  /** Null when the user has never explicitly saved per-stock parameters. */
  updated_at: string | null;
}

/** Body of `PUT /parameters` — every field is optional (partial update). */
export type ParameterUpdate = Partial<ParameterValues>;

export const parametersKey = (symbol: string) =>
  ["parameters", symbol.toUpperCase()] as const;

export function useParameters(symbol: string | undefined) {
  return useQuery({
    queryKey: symbol ? parametersKey(symbol) : ["parameters", "__none__"],
    queryFn: () =>
      api<ParameterRead>(`/api/stocks/${encodeURIComponent(symbol!)}/parameters`),
    enabled: Boolean(symbol),
  });
}

export function useUpdateParameters(symbol: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (patch: ParameterUpdate) =>
      api<ParameterRead>(
        `/api/stocks/${encodeURIComponent(symbol)}/parameters`,
        { method: "PUT", body: patch },
      ),
    onSuccess: (saved) => {
      queryClient.setQueryData(parametersKey(symbol), saved);
    },
  });
}
