/**
 * Snapshot Log (Task 23) — per-stock list of saved snapshots with detail
 * drawer + soft / hard delete actions.
 *
 * Filter toggle controls whether soft-deleted entries are shown; the
 * underlying query refetches on toggle thanks to a query key that
 * includes `include_deleted`.
 */

import { Eye, Trash2, Undo2 } from "lucide-react";
import { useState } from "react";

import { CollapsibleSection } from "@/components/CollapsibleSection";
import { GradeChip } from "@/components/GradeChip";
import { ApiError } from "@/lib/api";
import {
  useHardDeleteSnapshot,
  useSoftDeleteSnapshot,
  useStockSnapshots,
  type SnapshotListItem,
} from "@/lib/snapshots";
import { useAbbreviatedFormat } from "@/lib/settings";
import { cn } from "@/lib/utils";
import { useToast } from "@/stores/toast";

import { SnapshotDetailDialog } from "./SnapshotDetailDialog";

interface SnapshotLogProps {
  symbol: string;
  currency: string | null;
}

export function SnapshotLog({ symbol, currency }: SnapshotLogProps) {
  const [includeDeleted, setIncludeDeleted] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);

  const snapshotsQuery = useStockSnapshots(symbol, { includeDeleted });
  const softDelete = useSoftDeleteSnapshot();
  const hardDelete = useHardDeleteSnapshot();
  const toast = useToast();

  const snapshots = snapshotsQuery.data ?? [];

  async function handleSoftDelete(snapshot: SnapshotListItem) {
    const ok = window.confirm(
      `Soft-delete this snapshot from ${formatTimestamp(snapshot.created_at)}?\n\nIt will be hidden by default but can be restored only by hard-deleting and re-saving.`,
    );
    if (!ok) return;
    try {
      await softDelete.mutateAsync(snapshot.id);
      toast.show("Snapshot soft-deleted", { tone: "success" });
    } catch (err) {
      toast.show(
        err instanceof Error ? `Failed: ${err.message}` : "Failed to soft-delete.",
        { tone: "error" },
      );
    }
  }

  async function handleHardDelete(snapshot: SnapshotListItem) {
    const ok = window.confirm(
      `Hard-delete this snapshot? This permanently removes it and cannot be undone.`,
    );
    if (!ok) return;
    try {
      await hardDelete.mutateAsync(snapshot.id);
      toast.show("Snapshot deleted", { tone: "success" });
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        toast.show("Soft-delete the snapshot first.", { tone: "error" });
      } else {
        toast.show(
          err instanceof Error ? `Failed: ${err.message}` : "Failed to delete.",
          { tone: "error" },
        );
      }
    }
  }

  return (
    <>
      <CollapsibleSection
        title="Snapshot Log"
        trailing={
          <label className="flex cursor-pointer items-center gap-1.5 text-[11px] text-muted-foreground hover:text-foreground">
            <input
              type="checkbox"
              checked={includeDeleted}
              onChange={(e) => setIncludeDeleted(e.target.checked)}
              className="h-3 w-3"
            />
            Show deleted
          </label>
        }
      >
        {snapshotsQuery.isLoading ? (
          <p className="text-xs text-muted-foreground">Loading…</p>
        ) : snapshotsQuery.isError ? (
          <p className="text-xs text-destructive">
            Couldn't load snapshots. {(snapshotsQuery.error as Error).message}
          </p>
        ) : snapshots.length === 0 ? (
          <p className="text-[11px] text-muted-foreground">
            {includeDeleted
              ? "No snapshots — saved or deleted."
              : "No snapshots yet. Use Save Snapshot in the Parameter Panel to freeze the current analysis."}
          </p>
        ) : (
          <ul className="divide-y divide-border/60 rounded-md border border-border bg-card">
            {snapshots.map((snapshot) => (
              <SnapshotRow
                key={snapshot.id}
                snapshot={snapshot}
                currency={currency}
                onView={() => setDetailId(snapshot.id)}
                onSoftDelete={() => handleSoftDelete(snapshot)}
                onHardDelete={() => handleHardDelete(snapshot)}
                softDeletePending={softDelete.isPending}
                hardDeletePending={hardDelete.isPending}
              />
            ))}
          </ul>
        )}
      </CollapsibleSection>

      <SnapshotDetailDialog
        snapshotId={detailId}
        currency={currency}
        open={detailId !== null}
        onClose={() => setDetailId(null)}
      />
    </>
  );
}

// ---------------------------------------------------------------------------

interface SnapshotRowProps {
  snapshot: SnapshotListItem;
  currency: string | null;
  onView: () => void;
  onSoftDelete: () => void;
  onHardDelete: () => void;
  softDeletePending: boolean;
  hardDeletePending: boolean;
}

function SnapshotRow({
  snapshot,
  currency,
  onView,
  onSoftDelete,
  onHardDelete,
  softDeletePending,
  hardDeletePending,
}: SnapshotRowProps) {
  const formatAbbreviated = useAbbreviatedFormat();
  const isDeleted = snapshot.soft_deleted_at !== null;
  const fairValue =
    snapshot.average_fair_value === null
      ? null
      : Number(snapshot.average_fair_value);

  return (
    <li
      className={cn(
        "flex flex-wrap items-center gap-2 px-2 py-1 text-[11px] hover:bg-accent/40",
        isDeleted && "opacity-60",
      )}
    >
      <button
        type="button"
        onClick={onView}
        className="flex flex-1 flex-wrap items-center gap-2 text-left focus:outline-none focus:ring-1 focus:ring-ring"
        title="Open snapshot details"
      >
        <span className="min-w-[120px] font-mono tabular-nums text-muted-foreground">
          {formatTimestamp(snapshot.created_at)}
        </span>
        <GradeChip value={snapshot.general_grade} label="Gen" size="sm" />
        <span className="min-w-[80px] tabular-nums">
          {fairValue === null || !Number.isFinite(fairValue)
            ? "—"
            : (
                <>
                  <span className="text-muted-foreground">FV </span>
                  <span className="font-medium">
                    {formatAbbreviated(fairValue)}
                    {currency ? ` ${currency}` : ""}
                  </span>
                </>
              )}
        </span>
        <span className="flex-1 truncate text-muted-foreground" title={snapshot.note ?? undefined}>
          {snapshot.note ? snapshot.note : <span className="italic">No note</span>}
        </span>
        {isDeleted && (
          <span className="rounded bg-muted/40 px-1 py-0.5 text-[9px] uppercase tracking-wide text-muted-foreground">
            deleted
          </span>
        )}
      </button>
      <div className="flex items-center gap-0.5">
        <button
          type="button"
          onClick={onView}
          aria-label="View snapshot"
          title="View details"
          className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
        >
          <Eye className="h-3 w-3" />
        </button>
        {!isDeleted ? (
          <button
            type="button"
            onClick={onSoftDelete}
            disabled={softDeletePending}
            aria-label="Soft-delete snapshot"
            title="Soft-delete (hide from default view)"
            className="rounded p-1 text-muted-foreground hover:bg-warning/20 hover:text-warning focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
          >
            <Undo2 className="h-3 w-3" />
          </button>
        ) : (
          <button
            type="button"
            onClick={onHardDelete}
            disabled={hardDeletePending}
            aria-label="Hard-delete snapshot"
            title="Hard-delete (permanent)"
            className="rounded p-1 text-muted-foreground hover:bg-destructive/20 hover:text-destructive focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
          >
            <Trash2 className="h-3 w-3" />
          </button>
        )}
      </div>
    </li>
  );
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
