import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind class names safely (later classes win for the same property).
 * Used by every shadcn-style component going forward.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
