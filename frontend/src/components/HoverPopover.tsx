/**
 * Lightweight hover/focus popover.
 *
 * Wraps a trigger and shows the popover content while the user hovers
 * the trigger or its children, or while focus is within either of them.
 * Intentionally not a portal — callers should make sure the closest
 * scrolling ancestor isn't going to clip the panel.
 */

import { type ReactNode, useRef, useState } from "react";

import { cn } from "@/lib/utils";

interface HoverPopoverProps {
  content: ReactNode;
  /** Where to anchor the panel relative to the trigger. Default: top with right edge aligned. */
  placement?: "top-right" | "top-left" | "bottom-right" | "bottom-left";
  className?: string;
  panelClassName?: string;
  children: ReactNode;
}

const PLACEMENT_CLASSES: Record<NonNullable<HoverPopoverProps["placement"]>, string> = {
  "top-right": "bottom-full right-0 mb-1",
  "top-left": "bottom-full left-0 mb-1",
  "bottom-right": "top-full right-0 mt-1",
  "bottom-left": "top-full left-0 mt-1",
};

export function HoverPopover({
  content,
  placement = "top-right",
  className,
  panelClassName,
  children,
}: HoverPopoverProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLSpanElement>(null);

  // Use focus events on the wrapper so any focusable child opens the popover.
  function handleFocus(event: React.FocusEvent<HTMLSpanElement>) {
    if (containerRef.current?.contains(event.target)) setOpen(true);
  }
  function handleBlur(event: React.FocusEvent<HTMLSpanElement>) {
    if (!containerRef.current?.contains(event.relatedTarget as Node)) setOpen(false);
  }

  return (
    <span
      ref={containerRef}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={handleFocus}
      onBlur={handleBlur}
      className={cn("relative inline-block", className)}
    >
      {children}
      {open && (
        <span
          role="tooltip"
          className={cn(
            "absolute z-40 w-72 rounded-md border border-border bg-popover p-2 text-[11px] text-popover-foreground shadow-lg",
            PLACEMENT_CLASSES[placement],
            panelClassName,
          )}
        >
          {content}
        </span>
      )}
    </span>
  );
}
