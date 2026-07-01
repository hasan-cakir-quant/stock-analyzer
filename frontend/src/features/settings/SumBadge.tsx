import { cn } from "@/lib/utils";

interface SumBadgeProps {
  sum: number;
  expected?: number;
  className?: string;
}

/** Compact "current sum / expected" indicator that turns red when off-target. */
export function SumBadge({ sum, expected = 100, className }: SumBadgeProps) {
  const ok = sum === expected;
  return (
    <span
      role="status"
      aria-live="polite"
      title={ok ? "Sum is valid." : `Must equal ${expected}; currently ${sum}`}
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-medium tabular-nums",
        ok
          ? "border-success/30 bg-success/10 text-success"
          : "border-destructive/40 bg-destructive/10 text-destructive",
        className,
      )}
    >
      {sum} / {expected}
      {!ok && <span className="text-[10px]">(must sum to {expected})</span>}
    </span>
  );
}
