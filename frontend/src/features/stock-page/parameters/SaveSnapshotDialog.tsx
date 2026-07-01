/**
 * Tiny note-prompt before freezing a snapshot.
 *
 * Submits `POST /snapshots` with the supplied parameters override
 * (whatever the Parameter Panel currently has, including in-flight
 * unsaved edits) plus the optional note. The backend re-runs Full
 * Analysis server-side and persists everything atomically (Task 12).
 */

import { useState } from "react";

import { Modal } from "@/components/Modal";
import { useCreateSnapshot } from "@/lib/analysis";
import type { ParameterUpdate } from "@/lib/parameters";
import { useToast } from "@/stores/toast";

interface SaveSnapshotDialogProps {
  open: boolean;
  onClose: () => void;
  symbol: string;
  /** Snapshot is taken with these parameter overrides. */
  parameters: ParameterUpdate;
}

export function SaveSnapshotDialog({
  open,
  onClose,
  symbol,
  parameters,
}: SaveSnapshotDialogProps) {
  const createSnapshot = useCreateSnapshot(symbol);
  const toast = useToast();
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setNote("");
    setError(null);
    createSnapshot.reset();
  }

  function handleClose() {
    if (createSnapshot.isPending) return;
    reset();
    onClose();
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      await createSnapshot.mutateAsync({
        parameters,
        note: note.trim() === "" ? null : note.trim(),
      });
      toast.show("Snapshot saved", { tone: "success" });
      reset();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save snapshot.");
    }
  }

  return (
    <Modal open={open} onClose={handleClose} title="Save Snapshot" className="max-w-md">
      <form onSubmit={handleSubmit} className="space-y-2">
        <div className="flex flex-col gap-0.5">
          <label htmlFor="snapshot-note" className="text-[11px] text-muted-foreground">
            Optional note
          </label>
          <textarea
            id="snapshot-note"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            rows={3}
            placeholder="What changed? Why are you saving this?"
            className="w-full rounded-md border border-input bg-background px-1.5 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <p className="text-[10px] text-muted-foreground">
            Snapshot freezes the current quarterly data, parameters, and
            settings — they stay untouched even if you edit the originals later.
          </p>
        </div>

        {error && (
          <p role="alert" className="text-[11px] text-destructive">
            {error}
          </p>
        )}

        <div className="flex justify-end gap-1.5 pt-1">
          <button
            type="button"
            onClick={handleClose}
            disabled={createSnapshot.isPending}
            className="rounded-md border border-border bg-secondary px-2.5 py-1 text-[11px] text-secondary-foreground hover:bg-accent disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={createSnapshot.isPending}
            className="rounded-md bg-primary px-2.5 py-1 text-[11px] font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
          >
            {createSnapshot.isPending ? "Saving…" : "Save snapshot"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
