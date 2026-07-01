import { cn } from "@/lib/utils";

interface GradeChipProps {
  value: number | string | null | undefined;
  label?: string;
  size?: "sm" | "md" | "lg";
  /** Render "Incomplete" when value is null/undefined. */
  incompleteText?: string;
  className?: string;
  title?: string;
}

const SIZE_CLASSES: Record<NonNullable<GradeChipProps["size"]>, string> = {
  sm: "px-1 py-0.5 text-[9px]",
  md: "px-1.5 py-0.5 text-[11px]",
  lg: "px-2 py-0.5 text-xs",
};

function bandClasses(score: number): string {
  if (score >= 80) return "bg-success/15 text-success border-success/30";
  if (score >= 60) return "bg-warning/15 text-warning border-warning/30";
  if (score >= 40) return "bg-orange-500/15 text-orange-400 border-orange-500/30";
  return "bg-destructive/15 text-destructive border-destructive/30";
}

export function GradeChip({
  value,
  label,
  size = "md",
  incompleteText = "Incomplete",
  className,
  title,
}: GradeChipProps) {
  const numeric = value === null || value === undefined ? null : Number(value);
  const incomplete = numeric === null || !Number.isFinite(numeric);

  const text = incomplete
    ? incompleteText
    : `${label ? `${label}: ` : ""}${Math.round(numeric as number)}`;

  return (
    <span
      title={title ?? text}
      className={cn(
        "inline-flex items-center gap-1 rounded-md border font-medium tabular-nums",
        SIZE_CLASSES[size],
        incomplete
          ? "border-border bg-muted/40 text-muted-foreground"
          : bandClasses(numeric as number),
        className,
      )}
    >
      {text}
    </span>
  );
}
