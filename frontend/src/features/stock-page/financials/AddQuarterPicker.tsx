import { Plus } from "lucide-react";
import { useState } from "react";

import { formatQuarter, parseQuarter, previousQuarter } from "@/lib/quarters";
import { cn } from "@/lib/utils";

interface AddQuarterPickerProps {
  /** Periods already in the grid — used to suggest a sensible default and warn on duplicates. */
  existingPeriods: string[];
  onAdd: (period: string) => void;
}

const QUARTERS: ReadonlyArray<1 | 2 | 3 | 4> = [1, 2, 3, 4];

export function AddQuarterPicker({ existingPeriods, onAdd }: AddQuarterPickerProps) {
  const [open, setOpen] = useState(false);
  const initial = useDefaultQuarter(existingPeriods);
  const [year, setYear] = useState<string>(String(initial.year));
  const [q, setQ] = useState<1 | 2 | 3 | 4>(initial.q);
  const [error, setError] = useState<string | null>(null);

  const period = formatQuarter({ year: Number(year), q });
  const exists = existingPeriods.includes(period);
  const validYear = /^\d{4}$/.test(year);

  function handleAdd() {
    setError(null);
    if (!validYear) {
      setError("Year must be a 4-digit number.");
      return;
    }
    if (exists) {
      setError(`${period} is already in the grid.`);
      return;
    }
    onAdd(period);
    // Pre-load the next previous quarter so adding a backlog of older
    // quarters is one click each.
    const prior = previousQuarter(period);
    if (prior) {
      const parsed = parseQuarter(prior)!;
      setYear(String(parsed.year));
      setQ(parsed.q);
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1 rounded-md border border-border bg-secondary px-2 py-0.5 text-[11px] text-secondary-foreground hover:bg-accent"
      >
        <Plus className="h-3 w-3" />
        Add quarter
      </button>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5 rounded-md border border-border bg-card px-1.5 py-0.5">
      <input
        aria-label="Year"
        value={year}
        onChange={(e) => setYear(e.target.value.replace(/\D/g, "").slice(0, 4))}
        inputMode="numeric"
        className="h-6 w-14 rounded-md border border-input bg-background px-1.5 text-[11px] tabular-nums focus:outline-none focus:ring-1 focus:ring-ring"
      />
      <div className="inline-flex rounded-md border border-border bg-background p-0.5">
        {QUARTERS.map((value) => (
          <button
            key={value}
            type="button"
            onClick={() => setQ(value)}
            className={cn(
              "px-1.5 py-0.5 text-[11px]",
              q === value
                ? "rounded bg-secondary text-secondary-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            Q{value}
          </button>
        ))}
      </div>
      <button
        type="button"
        onClick={handleAdd}
        disabled={!validYear || exists}
        className="rounded-md bg-primary px-2 py-0.5 text-[11px] font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
      >
        Add {validYear ? period : "…"}
      </button>
      <button
        type="button"
        onClick={() => {
          setOpen(false);
          setError(null);
        }}
        className="rounded-md border border-border px-1.5 py-0.5 text-[11px] text-muted-foreground hover:bg-accent hover:text-foreground"
      >
        Done
      </button>
      {error && <span className="text-[10px] text-destructive">{error}</span>}
    </div>
  );
}

function useDefaultQuarter(existingPeriods: string[]): { year: number; q: 1 | 2 | 3 | 4 } {
  // If quarters exist, default to the one *before* the earliest so the user
  // can keep clicking "Add" to backfill history. Otherwise current quarter.
  if (existingPeriods.length === 0) {
    const now = new Date();
    return {
      year: now.getUTCFullYear(),
      q: (Math.floor(now.getUTCMonth() / 3) + 1) as 1 | 2 | 3 | 4,
    };
  }
  const earliest = [...existingPeriods].sort()[0];
  const earlierStill = previousQuarter(earliest);
  const parsed = earlierStill ? parseQuarter(earlierStill) : null;
  return parsed ?? { year: new Date().getUTCFullYear(), q: 1 };
}
