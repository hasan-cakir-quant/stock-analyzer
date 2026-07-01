/** Stocks query + mutation hooks. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";

export interface Stock {
  id: string;
  symbol: string;
  currency: string;
  shares_outstanding: string | null;
  notes: string | null;
  category: string | null;
  is_financial: boolean;
  units_note: string | null;
  cik: string | null;
  created_at: string;
  updated_at: string;
}

export interface StockCreate {
  symbol: string;
  currency: string;
  shares_outstanding?: string | number | null;
  notes?: string | null;
  category?: string | null;
  is_financial?: boolean;
  units_note?: string | null;
  cik?: string | null;
}

export type StockUpdate = Partial<Omit<StockCreate, "symbol">>;

export const stocksKey = ["stocks"] as const;
export const stockKey = (symbol: string) => ["stocks", symbol.toUpperCase()] as const;

export function useStocks() {
  return useQuery({
    queryKey: stocksKey,
    queryFn: () => api<Stock[]>("/api/stocks"),
  });
}

export function useStock(symbol: string | undefined) {
  return useQuery({
    queryKey: symbol ? stockKey(symbol) : ["stocks", "__none__"],
    queryFn: () => api<Stock>(`/api/stocks/${encodeURIComponent(symbol!)}`),
    enabled: Boolean(symbol),
    retry: false,
  });
}

export function useCreateStock() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: StockCreate) =>
      api<Stock>("/api/stocks", { method: "POST", body: payload }),
    onSuccess: (created) => {
      queryClient.setQueryData(stockKey(created.symbol), created);
      queryClient.invalidateQueries({ queryKey: stocksKey });
    },
  });
}

export function useUpdateStock(symbol: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: StockUpdate) =>
      api<Stock>(`/api/stocks/${encodeURIComponent(symbol)}`, {
        method: "PATCH",
        body: payload,
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(stockKey(updated.symbol), updated);
      queryClient.invalidateQueries({ queryKey: stocksKey });
    },
  });
}

export function useLookupCik(symbol: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      api<Stock>(`/api/stocks/${encodeURIComponent(symbol)}/cik/lookup`, {
        method: "POST",
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(stockKey(updated.symbol), updated);
      queryClient.invalidateQueries({ queryKey: stocksKey });
    },
  });
}
