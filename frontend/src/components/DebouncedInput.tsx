import { useEffect, useId, useRef, useState } from "react";

import { SaveIndicator, type SaveState } from "@/components/SaveIndicator";
import { cn } from "@/lib/utils";

interface DebouncedInputProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "onChange" | "value"> {
  value: string;
  onSave: (value: string) => void | Promise<void>;
  debounceMs?: number;
  /** Hide the inline `<SaveIndicator />` (e.g. in grids that show their own state). */
  hideIndicator?: boolean;
  label?: string;
  containerClassName?: string;
  /**
   * Fires on every keystroke (no debounce). Use this when the parent
   * needs to track the in-flight value before it's persisted — e.g. the
   * Parameter Panel mirrors the draft so Run Full Analysis can use the
   * latest typed value even within the 500 ms save window.
   */
  onValueChange?: (value: string) => void;
}

const SAVED_STATE_HOLD_MS = 1500;

export function DebouncedInput({
  value,
  onSave,
  onValueChange,
  debounceMs = 500,
  hideIndicator,
  label,
  containerClassName,
  className,
  id: providedId,
  ...inputProps
}: DebouncedInputProps) {
  const generatedId = useId();
  const id = providedId ?? generatedId;
  const [local, setLocal] = useState(value);
  const [state, setState] = useState<SaveState>("idle");
  const debounceTimer = useRef<number | null>(null);
  const savedHoldTimer = useRef<number | null>(null);
  const lastSavedRef = useRef(value);

  // Pull in updates from the source of truth (e.g. server refetch) only
  // when the user isn't mid-edit — avoids stomping the in-flight value.
  useEffect(() => {
    if (state === "idle" || state === "saved") {
      setLocal(value);
      lastSavedRef.current = value;
    }
  }, [value, state]);

  useEffect(() => {
    return () => {
      if (debounceTimer.current) window.clearTimeout(debounceTimer.current);
      if (savedHoldTimer.current) window.clearTimeout(savedHoldTimer.current);
    };
  }, []);

  function scheduleSave(next: string) {
    if (debounceTimer.current) window.clearTimeout(debounceTimer.current);
    debounceTimer.current = window.setTimeout(async () => {
      if (next === lastSavedRef.current) {
        setState("idle");
        return;
      }
      setState("saving");
      try {
        await Promise.resolve(onSave(next));
        lastSavedRef.current = next;
        setState("saved");
        if (savedHoldTimer.current) window.clearTimeout(savedHoldTimer.current);
        savedHoldTimer.current = window.setTimeout(
          () => setState("idle"),
          SAVED_STATE_HOLD_MS,
        );
      } catch {
        setState("error");
      }
    }, debounceMs);
  }

  function handleChange(event: React.ChangeEvent<HTMLInputElement>) {
    const next = event.target.value;
    setLocal(next);
    onValueChange?.(next);
    scheduleSave(next);
  }

  return (
    <div className={cn("flex flex-col gap-0.5", containerClassName)}>
      {label && (
        <label htmlFor={id} className="text-[11px] text-muted-foreground">
          {label}
        </label>
      )}
      <div className="flex items-center gap-1.5">
        <input
          {...inputProps}
          id={id}
          value={local}
          onChange={handleChange}
          className={cn(
            "h-7 w-full rounded-md border border-input bg-background px-1.5 text-xs",
            "focus:outline-none focus:ring-2 focus:ring-ring",
            state === "error" && "border-destructive",
            className,
          )}
        />
        {!hideIndicator && <SaveIndicator state={state} />}
      </div>
    </div>
  );
}
