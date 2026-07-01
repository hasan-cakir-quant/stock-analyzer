/**
 * Settings query + format hooks.
 *
 * `useSettings()` is the canonical fetcher for the singleton settings row
 * and is shared across pages; `useNumberFormat` / `useCurrencyFormat` /
 * `usePercentFormat` are thin wrappers that pull `currency_format` out
 * and bind it into a stable callback.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";

import { api } from "@/lib/api";
import {
  type CurrencyFormat,
  FALLBACK_CURRENCY_FORMAT,
  formatAbbreviated,
  formatCurrency,
  formatNumber,
  formatPercent,
} from "@/lib/format";

export interface Settings {
  id: number;
  general_grade_weights: Record<string, number | string>;
  sub_grade_weights: Record<string, Record<string, number | string>>;
  grade_thresholds: Record<string, unknown>;
  currency_format: CurrencyFormat;
  global_market_assumptions: Record<string, string | number | boolean | null>;
  updated_at: string;
}

/** Body shape for `PUT /api/settings` — full replace, no `id` / `updated_at`. */
export type SettingsUpdate = Omit<Settings, "id" | "updated_at">;

export const SETTINGS_QUERY_KEY = ["settings"] as const;

export function useSettings() {
  return useQuery({
    queryKey: SETTINGS_QUERY_KEY,
    queryFn: () => api<Settings>("/api/settings"),
  });
}

export function useUpdateSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SettingsUpdate) =>
      api<Settings>("/api/settings", { method: "PUT", body: payload }),
    onSuccess: (data) => {
      queryClient.setQueryData(SETTINGS_QUERY_KEY, data);
    },
  });
}

function useFormatConfig(): CurrencyFormat {
  const { data } = useSettings();
  return data?.currency_format ?? FALLBACK_CURRENCY_FORMAT;
}

export function useNumberFormat() {
  const format = useFormatConfig();
  return useCallback(
    (value: number | string | null | undefined, options?: { decimalPlaces?: number }) =>
      formatNumber(value, format, options),
    [format],
  );
}

export function useCurrencyFormat() {
  const format = useFormatConfig();
  return useCallback(
    (value: number | string | null | undefined, currency?: string | null) =>
      formatCurrency(value, format, currency),
    [format],
  );
}

export function usePercentFormat() {
  const format = useFormatConfig();
  return useCallback(
    (
      value: number | string | null | undefined,
      options?: { fromFraction?: boolean; decimalPlaces?: number },
    ) => formatPercent(value, format, options),
    [format],
  );
}

export function useAbbreviatedFormat() {
  const format = useFormatConfig();
  return useCallback(
    (
      value: number | string | null | undefined,
      options?: { decimalPlaces?: number },
    ) => formatAbbreviated(value, format, options),
    [format],
  );
}
