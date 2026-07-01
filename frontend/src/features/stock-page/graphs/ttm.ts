/** Shared trailing-twelve-month helpers for the history graphs. */

export const TTM_QUARTERS = 4;

/**
 * Fill *isolated* single-quarter gaps by linear interpolation of the nearest
 * neighbors (a null with reported values immediately on both sides). Runs of
 * two or more consecutive nulls are left as gaps.
 */
export function fillIsolatedGaps(series: (number | null)[]): (number | null)[] {
  const out = series.slice();
  for (let i = 0; i < out.length; i += 1) {
    if (out[i] !== null) continue;
    const prev = i > 0 ? series[i - 1] : null;
    const next = i < series.length - 1 ? series[i + 1] : null;
    if (prev !== null && next !== null) {
      out[i] = (prev + next) / 2;
    }
  }
  return out;
}

/**
 * Trailing-twelve-month sum ending at index `i` over a (gap-filled) series.
 * Returns null until a full window of finite values is available.
 */
export function trailingTtm(filled: (number | null)[], i: number): number | null {
  if (i < TTM_QUARTERS - 1) return null;
  const window = filled.slice(i - TTM_QUARTERS + 1, i + 1);
  if (!window.every((v) => v !== null && Number.isFinite(v))) return null;
  return (window as number[]).reduce((acc, v) => acc + v, 0);
}

/**
 * Simple moving average of `series` over `window` periods ending at index `i`.
 * Returns null until a full window of finite values is available.
 */
export function movingAverageAt(
  series: (number | null)[],
  i: number,
  window: number,
): number | null {
  if (i < window - 1) return null;
  const slice = series.slice(i - window + 1, i + 1);
  if (!slice.every((v) => v !== null && Number.isFinite(v))) return null;
  return (slice as number[]).reduce((acc, v) => acc + v, 0) / window;
}
