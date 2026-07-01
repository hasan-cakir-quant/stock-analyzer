import { CheckCircle2, Info, X, XCircle } from "lucide-react";

import { cn } from "@/lib/utils";
import { type ToastTone, useToastStore } from "@/stores/toast";

const TONE_CLASSES: Record<ToastTone, string> = {
  info: "border-border bg-card text-card-foreground",
  success: "border-success/40 bg-card text-foreground",
  error: "border-destructive/50 bg-card text-foreground",
};

const TONE_ICONS: Record<ToastTone, typeof Info> = {
  info: Info,
  success: CheckCircle2,
  error: XCircle,
};

const TONE_ICON_COLORS: Record<ToastTone, string> = {
  info: "text-muted-foreground",
  success: "text-success",
  error: "text-destructive",
};

export function Toaster() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);

  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-full max-w-sm flex-col gap-2"
    >
      {toasts.map((toast) => {
        const Icon = TONE_ICONS[toast.tone];
        return (
          <div
            key={toast.id}
            role="status"
            className={cn(
              "pointer-events-auto flex items-center gap-2 rounded-md border px-3 py-2 text-sm shadow-lg",
              TONE_CLASSES[toast.tone],
            )}
          >
            <Icon className={cn("h-4 w-4 shrink-0", TONE_ICON_COLORS[toast.tone])} />
            <span className="flex-1">{toast.message}</span>
            <button
              type="button"
              onClick={() => dismiss(toast.id)}
              className="rounded p-0.5 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
              aria-label="Dismiss"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
