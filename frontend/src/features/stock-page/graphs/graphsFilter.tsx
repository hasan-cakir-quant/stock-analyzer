/**
 * Shared "last N quarters" filter for the Graphs section. The section owns the
 * selected window and broadcasts it via context; each chart applies the cutoff
 * to its *own* series at render time (after MA/TTM math) so the moving averages
 * stay correct for the visible window. `null` means "all quarters".
 */

import { createContext, useContext } from "react";

/** Quick-pick windows offered in the section header. `null` = All. */
export const QUARTER_WINDOWS: (number | null)[] = [null, 8, 12, 16, 20];

const GraphsFilterContext = createContext<number | null>(null);

export const GraphsFilterProvider = GraphsFilterContext.Provider;

/** Number of trailing quarters to show, or `null` for all. */
export function useMaxQuarters(): number | null {
  return useContext(GraphsFilterContext);
}

/**
 * Keep only the trailing `maxQuarters` rows of an already-ordered (oldest →
 * newest) series. Returns the input unchanged when no window is set.
 */
export function clampToWindow<T>(rows: T[], maxQuarters: number | null): T[] {
  return maxQuarters && maxQuarters < rows.length ? rows.slice(-maxQuarters) : rows;
}
