import { useEffect, useId, useRef, useState } from "react";

import { SaveIndicator, type SaveState } from "@/components/SaveIndicator";
import { cn } from "@/lib/utils";

interface DebouncedTextareaProps
  extends Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, "onChange" | "value"> {
  value: string;
  onSave: (value: string) => void | Promise<void>;
  debounceMs?: number;
  hideIndicator?: boolean;
  label?: string;
  containerClassName?: string;
}

const SAVED_STATE_HOLD_MS = 1500;

export function DebouncedTextarea({
  value,
  onSave,
  debounceMs = 500,
  hideIndicator,
  label,
  containerClassName,
  className,
  id: providedId,
  ...textareaProps
}: DebouncedTextareaProps) {
  const generatedId = useId();
  const id = providedId ?? generatedId;
  const [local, setLocal] = useState(value);
  const [state, setState] = useState<SaveState>("idle");
  const debounceTimer = useRef<number | null>(null);
  const savedHoldTimer = useRef<number | null>(null);
  const lastSavedRef = useRef(value);

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

  function handleChange(event: React.ChangeEvent<HTMLTextAreaElement>) {
    const next = event.target.value;
    setLocal(next);
    scheduleSave(next);
  }

  return (
    <div className={cn("flex flex-col gap-1", containerClassName)}>
      {label && (
        <label htmlFor={id} className="text-xs text-muted-foreground">
          {label}
        </label>
      )}
      <textarea
        {...textareaProps}
        id={id}
        value={local}
        onChange={handleChange}
        className={cn(
          "w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm",
          "focus:outline-none focus:ring-2 focus:ring-ring",
          state === "error" && "border-destructive",
          className,
        )}
      />
      {!hideIndicator && <SaveIndicator state={state} />}
    </div>
  );
}
