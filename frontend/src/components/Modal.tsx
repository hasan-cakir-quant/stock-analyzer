import { X } from "lucide-react";
import { type ReactNode, useEffect } from "react";
import { createPortal } from "react-dom";

import { cn } from "@/lib/utils";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  /** Width override; defaults to a comfortable form size. */
  className?: string;
  children: ReactNode;
}

export function Modal({ open, onClose, title, className, children }: ModalProps) {
  // Lock body scroll + close on Escape while the modal is mounted.
  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);

    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={typeof title === "string" ? "modal-title" : undefined}
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 p-4"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className={cn(
          "mt-8 w-full max-w-lg rounded-lg border border-border bg-card text-card-foreground shadow-xl",
          className,
        )}
      >
        <header className="flex items-center justify-between border-b border-border px-3 py-2">
          {typeof title === "string" ? (
            <h2 id="modal-title" className="text-sm font-semibold">
              {title}
            </h2>
          ) : (
            <div>{title}</div>
          )}
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-md p-0.5 text-muted-foreground hover:bg-accent hover:text-accent-foreground"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </header>
        <div className="px-3 py-2.5">{children}</div>
      </div>
    </div>,
    document.body,
  );
}
