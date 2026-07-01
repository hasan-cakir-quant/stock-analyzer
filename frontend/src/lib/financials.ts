/** Quarterly financials query + per-quarter upsert hooks. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";

/**
 * Server response shape for one quarter — keys mirror the backend
 * Pydantic schema. Numeric values arrive as JSON strings (Decimal).
 */
export interface FinancialRow {
  id: string;
  stock_id: string;
  period: string;
  period_end_date: string | null;
  updated_at: string;

  revenue: string | null;
  cogs: string | null;
  gross_profit: string | null;
  operating_expenses: string | null;
  operating_income: string | null;
  interest_expense: string | null;
  pretax_income: string | null;
  net_income: string | null;
  eps_basic: string | null;
  eps_diluted: string | null;
  ebitda: string | null;
  shares_outstanding_diluted: string | null;

  cash_and_equivalents: string | null;
  short_term_investments: string | null;
  total_current_assets: string | null;
  total_assets: string | null;
  short_term_debt: string | null;
  total_current_liabilities: string | null;
  long_term_debt: string | null;
  total_liabilities: string | null;
  total_equity: string | null;
  inventory: string | null;
  receivables: string | null;

  operating_cash_flow: string | null;
  capex: string | null;
  free_cash_flow: string | null;
  dividends_paid: string | null;
  stock_buybacks: string | null;

  closing_price: string | null;
}

export type FinancialField = Exclude<
  keyof FinancialRow,
  "id" | "stock_id" | "period" | "updated_at"
>;

export type FinancialUpsert = Partial<Omit<FinancialRow, "id" | "stock_id" | "period" | "updated_at">>;

export const financialsKey = (symbol: string) =>
  ["financials", symbol.toUpperCase()] as const;

export function useFinancials(symbol: string | undefined) {
  return useQuery({
    queryKey: symbol ? financialsKey(symbol) : ["financials", "__none__"],
    queryFn: () =>
      api<FinancialRow[]>(`/api/stocks/${encodeURIComponent(symbol!)}/financials`),
    enabled: Boolean(symbol),
  });
}

export function useUpsertFinancial(symbol: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ period, body }: { period: string; body: FinancialUpsert }) =>
      api<FinancialRow>(
        `/api/stocks/${encodeURIComponent(symbol)}/financials/${encodeURIComponent(period)}`,
        { method: "PUT", body },
      ),
    onSuccess: (saved) => {
      const key = financialsKey(symbol);
      queryClient.setQueryData<FinancialRow[]>(key, (current) => {
        if (!current) return [saved];
        const idx = current.findIndex((r) => r.period === saved.period);
        if (idx === -1) return [...current, saved].sort((a, b) => a.period.localeCompare(b.period));
        const next = current.slice();
        next[idx] = saved;
        return next;
      });
    },
  });
}

export function useDeleteFinancial(symbol: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (period: string) =>
      api<void>(
        `/api/stocks/${encodeURIComponent(symbol)}/financials/${encodeURIComponent(period)}`,
        { method: "DELETE" },
      ),
    onSuccess: (_, period) => {
      const key = financialsKey(symbol);
      queryClient.setQueryData<FinancialRow[]>(key, (current) =>
        (current ?? []).filter((r) => r.period !== period),
      );
    },
  });
}

// ---------------------------------------------------------------------------
// HTML import
// ---------------------------------------------------------------------------

export interface ImportSource {
  id: string;
  source: string;
  statement: "income" | "balance" | "cashflow" | "all";
  label: string;
}

export interface ImportRowPreview {
  period: string;
  period_end_date: string | null;
  fields: Record<string, string>;
  // Source label → source value (in source units). Sent through to
  // bulk-upsert so the backend can archive the full payload in
  // `financial_imports`, including labels we don't have a column for.
  raw_source: Record<string, string>;
}

export interface ImportPreview {
  parser_id: string;
  source: string;
  statement: ImportSource["statement"];
  caption: string | null;
  rows: ImportRowPreview[];
  unmapped_labels: string[];
  warnings: string[];
}

export interface ImportContext {
  parser_id: string;
  source: string;
  statement: ImportSource["statement"];
  caption: string | null;
}

export function useImportSources() {
  return useQuery({
    queryKey: ["import-sources"],
    queryFn: () => api<ImportSource[]>("/api/imports/sources"),
    // Short stale window so newly-registered parsers show up on the
    // next dialog open without forcing a hard refresh.
    staleTime: 10_000,
  });
}

export function useImportPreview(symbol: string) {
  return useMutation({
    mutationFn: async ({ parserId, file }: { parserId: string; file: File }) => {
      const body = new FormData();
      body.append("parser_id", parserId);
      body.append("file", file);
      return api<ImportPreview>(
        `/api/stocks/${encodeURIComponent(symbol)}/financials/import-preview`,
        { method: "POST", body, rawBody: true },
      );
    },
  });
}

/** Live fetch from SEC EDGAR — pulls XBRL companyfacts for the stock's
 * saved CIK and returns the same preview shape as the file-upload path. */
export function useImportFromEdgar(symbol: string) {
  return useMutation({
    mutationFn: () =>
      api<ImportPreview>(
        `/api/stocks/${encodeURIComponent(symbol)}/financials/import-preview-edgar`,
        { method: "POST" },
      ),
  });
}

export interface BulkUpsertRow {
  period: string;
  raw_source?: Record<string, string>;
  [field: string]: string | null | undefined | Record<string, string>;
}

export interface BulkUpsertResponse {
  written: number;
  periods: string[];
  raw_payloads_archived: number;
}

export interface BulkUpsertVariables {
  rows: BulkUpsertRow[];
  importContext?: ImportContext;
}

// ---------------------------------------------------------------------------
// Market data — EoQ closing prices
// ---------------------------------------------------------------------------

export interface ClosingPriceEntry {
  period: string;
  end_date: string;
  closing_price: string | null;
  reason?: string | null;
}

export interface ClosingPricesResponse {
  symbol: string;
  source: string;
  prices: ClosingPriceEntry[];
}

export function useFetchClosingPrices(symbol: string) {
  return useMutation({
    mutationFn: (periods?: string[]) => {
      const query =
        periods && periods.length
          ? `?${periods.map((p) => `periods=${encodeURIComponent(p)}`).join("&")}`
          : "";
      return api<ClosingPricesResponse>(
        `/api/stocks/${encodeURIComponent(symbol)}/market-data/closing-prices${query}`,
      );
    },
  });
}

export function useBulkUpsertFinancials(symbol: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ rows, importContext }: BulkUpsertVariables) =>
      api<BulkUpsertResponse>(
        `/api/stocks/${encodeURIComponent(symbol)}/financials/bulk-upsert`,
        {
          method: "POST",
          body: {
            rows,
            ...(importContext ? { import_context: importContext } : {}),
          },
        },
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: financialsKey(symbol) });
    },
  });
}
