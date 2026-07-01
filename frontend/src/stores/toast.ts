/**
 * Tiny toast primitive — Zustand store + auto-dismiss timer.
 *
 * Used for save-state feedback ("Saving…" / "Saved ✓" / "Error — retry").
 * The shape mirrors what shadcn's Sonner exposes so we can swap in the real
 * thing later without touching call sites.
 */

import { create } from "zustand";

export type ToastTone = "info" | "success" | "error";

export interface Toast {
  id: string;
  message: string;
  tone: ToastTone;
  // Stored so the renderer can clear timers on manual dismiss.
  dismissAt: number;
}

interface ToastShowOptions {
  tone?: ToastTone;
  durationMs?: number;
}

interface ToastApi {
  show: (message: string, options?: ToastShowOptions) => string;
  dismiss: (id: string) => void;
}

interface ToastStore {
  toasts: Toast[];
  show: ToastApi["show"];
  dismiss: ToastApi["dismiss"];
}

const DEFAULT_DURATION_MS = 3000;
let counter = 0;

export const useToastStore = create<ToastStore>((set) => ({
  toasts: [],
  show: (message, options) => {
    const id = `t${Date.now()}-${counter++}`;
    const tone = options?.tone ?? "info";
    const duration = options?.durationMs ?? DEFAULT_DURATION_MS;
    const toast: Toast = { id, message, tone, dismissAt: Date.now() + duration };
    set((state) => ({ toasts: [...state.toasts, toast] }));
    if (duration > 0) {
      setTimeout(() => {
        set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
      }, duration);
    }
    return id;
  },
  dismiss: (id) =>
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
}));

/** Hook for components that just want to fire toasts (no need for the list).
 * Selects each function individually — returning a fresh `{show, dismiss}`
 * object from one selector triggers a re-render loop because Zustand sees
 * the new reference as a change.
 */
export function useToast(): ToastApi {
  const show = useToastStore((state) => state.show);
  const dismiss = useToastStore((state) => state.dismiss);
  return { show, dismiss };
}
