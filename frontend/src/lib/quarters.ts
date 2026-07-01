/** Quarter-string helpers — `YYYY-Qn` form per the backend's PERIOD_PATTERN. */

export const PERIOD_REGEX = /^(\d{4})-Q([1-4])$/;

export interface Quarter {
  year: number;
  q: 1 | 2 | 3 | 4;
}

export function parseQuarter(period: string): Quarter | null {
  const match = PERIOD_REGEX.exec(period);
  if (!match) return null;
  return { year: Number(match[1]), q: Number(match[2]) as Quarter["q"] };
}

export function formatQuarter({ year, q }: Quarter): string {
  return `${year}-Q${q}`;
}

export function nextQuarter(period: string): string | null {
  const parsed = parseQuarter(period);
  if (!parsed) return null;
  if (parsed.q === 4) return formatQuarter({ year: parsed.year + 1, q: 1 });
  return formatQuarter({ year: parsed.year, q: (parsed.q + 1) as Quarter["q"] });
}

export function previousQuarter(period: string): string | null {
  const parsed = parseQuarter(period);
  if (!parsed) return null;
  if (parsed.q === 1) return formatQuarter({ year: parsed.year - 1, q: 4 });
  return formatQuarter({ year: parsed.year, q: (parsed.q - 1) as Quarter["q"] });
}

/** Lex order works since `YYYY-Qn` is monotone. */
export function compareQuarters(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

/** Today's calendar quarter (used as a starting point for new entries). */
export function currentQuarter(date: Date = new Date()): string {
  const q = (Math.floor(date.getUTCMonth() / 3) + 1) as Quarter["q"];
  return formatQuarter({ year: date.getUTCFullYear(), q });
}
