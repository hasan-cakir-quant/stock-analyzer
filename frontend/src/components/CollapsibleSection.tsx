import { ChevronDown } from "lucide-react";
import { type ReactNode, useState } from "react";

import { cn } from "@/lib/utils";

interface CollapsibleSectionProps {
  title: ReactNode;
  /** Optional right-aligned content shown next to the title (e.g. SaveIndicator). */
  trailing?: ReactNode;
  defaultOpen?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  className?: string;
  children: ReactNode;
}

export function CollapsibleSection({
  title,
  trailing,
  defaultOpen = true,
  open: controlledOpen,
  onOpenChange,
  className,
  children,
}: CollapsibleSectionProps) {
  const [internalOpen, setInternalOpen] = useState(defaultOpen);
  const isControlled = controlledOpen !== undefined;
  const open = isControlled ? controlledOpen : internalOpen;

  function toggle() {
    const next = !open;
    if (!isControlled) setInternalOpen(next);
    onOpenChange?.(next);
  }

  return (
    <section
      className={cn(
        "rounded-md border border-border bg-card text-card-foreground shadow-sm",
        className,
      )}
    >
      <header className="flex items-center justify-between gap-2 px-2 py-1">
        <button
          type="button"
          onClick={toggle}
          aria-expanded={open}
          className="flex flex-1 items-center gap-1.5 text-left text-xs font-medium hover:text-primary"
        >
          <ChevronDown
            className={cn(
              "h-3.5 w-3.5 transition-transform",
              open ? "rotate-0" : "-rotate-90",
            )}
          />
          {title}
        </button>
        {trailing}
      </header>
      {open && <div className="border-t border-border px-2 py-1.5">{children}</div>}
    </section>
  );
}
