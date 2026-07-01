/**
 * Value area of a set of fair-value estimates.
 *
 * Borrowed from market-profile analysis: the "value area" is the central band
 * of the distribution once the outlier tails are trimmed. Here it's the central
 * 70% — drop the lowest 15% and highest 15% of estimates — and the headline
 * number is the *mean of what's left* (a 70% trimmed mean), which is robust to
 * a single method blowing out (e.g. EV/FCF). This is the value used for the MA
 * snapshot and drawn on the fair-value distribution.
 */

/** Fraction of the distribution kept inside the value area. */
export const VALUE_AREA_COVERAGE = 0.7;

export interface ValueArea {
  /** Lower edge of the value area (15th percentile). */
  low: number;
  /** Upper edge of the value area (85th percentile). */
  high: number;
  /** Mean of the estimates inside [low, high] — the headline fair value. */
  mean: number;
  /** How many estimates fell inside the value area. */
  count: number;
}

/** Linear-interpolated quantile of an ascending-sorted array. */
function quantileSorted(sorted: number[], q: number): number {
  if (sorted.length === 1) return sorted[0];
  const pos = (sorted.length - 1) * q;
  const base = Math.floor(pos);
  const rest = pos - base;
  const next = sorted[base + 1];
  return next !== undefined ? sorted[base] + rest * (next - sorted[base]) : sorted[base];
}

/**
 * Compute the value area of `values`. Returns null if there are no finite
 * values. `coverage` is the fraction kept (default 70%).
 */
export function computeValueArea(
  values: number[],
  coverage = VALUE_AREA_COVERAGE,
): ValueArea | null {
  const finite = values
    .filter((v) => Number.isFinite(v))
    .slice()
    .sort((a, b) => a - b);
  if (finite.length === 0) return null;

  const tail = (1 - coverage) / 2; // 0.15 for 70% coverage
  const low = quantileSorted(finite, tail);
  const high = quantileSorted(finite, 1 - tail);

  const inArea = finite.filter((v) => v >= low && v <= high);
  // Guard the degenerate case (e.g. all values equal, or only 1-2 points) where
  // the percentile band collapses to nothing — fall back to the full set.
  const area = inArea.length > 0 ? inArea : finite;
  const mean = area.reduce((acc, v) => acc + v, 0) / area.length;

  return { low, high, mean, count: area.length };
}
