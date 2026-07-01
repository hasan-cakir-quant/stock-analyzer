import { AlertCircle, Check, Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

export type SaveState = "idle" | "saving" | "saved" | "error";

interface SaveIndicatorProps {
  state: SaveState;
  className?: string;
}

const COPY: Record<Exclude<SaveState, "idle">, string> = {
  saving: "Saving…",
  saved: "Saved",
  error: "Error — retry",
};

export function SaveIndicator({ state, className }: SaveIndicatorProps) {
  if (state === "idle") {
    // Reserve the space so layouts don't jump when the indicator appears.
    return <span aria-hidden className={cn("inline-block h-4 w-4", className)} />;
  }

  return (
    <span
      role="status"
      className={cn(
        "inline-flex items-center gap-1 text-xs",
        state === "saving" && "text-muted-foreground",
        state === "saved" && "text-success",
        state === "error" && "text-destructive",
        className,
      )}
    >
      {state === "saving" && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
      {state === "saved" && <Check className="h-3.5 w-3.5" />}
      {state === "error" && <AlertCircle className="h-3.5 w-3.5" />}
      <span>{COPY[state]}</span>
    </span>
  );
}
