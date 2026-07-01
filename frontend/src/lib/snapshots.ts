/**
 * Snapshots — list / detail hooks plus soft + hard delete mutations.
 *
 * The list hook supports `include_deleted` so the Snapshot Log on the
 * stock page can toggle visibility without re-mounting. Both delete
 * mutations invalidate every snapshot query (per-stock + cross-stock)
 * since a single delete affects both views.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { api } from "@/lib/api";

export interface SnapshotListItem {
  id: string;
  stock_id: string;
  symbol: string;
  created_at: string;
  note: string | null;
  current_price_used: string | null;
  soft_deleted_at: string | null;
  general_grade: string | null;
  average_fair_value: string | null;
}

export interface MaValuationWindow {
  window: number;
  multiple: number | null;
  fair_value: number | null;
}

export interface MaValuationMethod {
  key: string;
  label: string;
  windows: MaValuationWindow[];
}

export interface MaValueArea {
  low: number;
  high: number;
  /** Mean of the value area — the headline fair value for the snapshot. */
  mean: number;
  count: number;
}

export interface MaValuations {
  scenario: string;
  scenario_label: string;
  factor: number;
  current_price: number | null;
  /** Central-70% value area of the fair-value cells (null for older snapshots). */
  value_area?: MaValueArea | null;
  methods: MaValuationMethod[];
}

export interface Snapshot extends SnapshotListItem {
  financials_snapshot: Array<Record<string, unknown>>;
  parameters_used: Record<string, unknown>;
  settings_used: Record<string, unknown>;
  valuations: Record<string, unknown>;
  grades: Record<string, unknown>;
  growth_metrics: Record<string, unknown>;
  ma_valuations: MaValuations | null;
}

export const snapshotsKey = (
  symbol: string,
  options: { includeDeleted?: boolean } = {},
) => ["snapshots", symbol.toUpperCase(), options.includeDeleted ?? false] as const;

export const snapshotKey = (id: string) => ["snapshot", id] as const;

export interface UseStockSnapshotsOptions {
  /** Include snapshots whose `soft_deleted_at` is non-null. Defaults to false. */
  includeDeleted?: boolean;
}

export function useStockSnapshots(
  symbol: string | undefined,
  options: UseStockSnapshotsOptions = {},
) {
  const includeDeleted = options.includeDeleted ?? false;
  return useQuery({
    queryKey: symbol ? snapshotsKey(symbol, { includeDeleted }) : ["snapshots", "__none__"],
    queryFn: () => {
      const url = `/api/stocks/${encodeURIComponent(symbol!)}/snapshots${
        includeDeleted ? "?include_deleted=true" : ""
      }`;
      return api<SnapshotListItem[]>(url);
    },
    enabled: Boolean(symbol),
  });
}

export function useSnapshotDetail(snapshotId: string | null) {
  return useQuery({
    queryKey: snapshotId ? snapshotKey(snapshotId) : ["snapshot", "__none__"],
    queryFn: () => api<Snapshot>(`/api/snapshots/${encodeURIComponent(snapshotId!)}`),
    enabled: Boolean(snapshotId),
  });
}

function invalidateAllSnapshotQueries(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: ["snapshots"] });
  queryClient.invalidateQueries({ queryKey: ["snapshot"] });
}

/** Soft-delete: stamps `soft_deleted_at` on the server. Idempotent. */
export function useSoftDeleteSnapshot() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (snapshotId: string) =>
      api<void>(`/api/snapshots/${encodeURIComponent(snapshotId)}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidateAllSnapshotQueries(queryClient),
  });
}

/** Hard-delete: server returns 409 if the snapshot isn't soft-deleted yet. */
export function useHardDeleteSnapshot() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (snapshotId: string) =>
      api<void>(`/api/snapshots/${encodeURIComponent(snapshotId)}/hard`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidateAllSnapshotQueries(queryClient),
  });
}
