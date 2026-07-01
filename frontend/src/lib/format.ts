/**
 * Number / currency / percentage formatting that honours the user's chosen
 * thousands separator, decimal separator, and decimal places (FR-3.9.3).
 */

export interface CurrencyFormat {
  thousands_separator: string;
  decimal_separator: string;
  decimal_places: number;
}

export const FALLBACK_CURRENCY_FORMAT: CurrencyFormat = {
  thousands_separator: ",",
  decimal_separator: ".",
  decimal_places: 2,
};

export const NA = "—";

// Sentinel char that won't appear in numeric input — used to mark thousands
// boundaries so we can swap in any user-chosen separator (including `$`,
// which would otherwise be interpreted as a regex backreference).
const THOUSANDS_SENTINEL = "\x00";

function applyFormat(
  value: number,
  format: CurrencyFormat,
  decimalPlacesOverride?: number,
): string {
  const places = decimalPlacesOverride ?? format.decimal_places;
  const fixed = value.toFixed(places);
  const negative = fixed.startsWith("-");
  const magnitude = negative ? fixed.slice(1) : fixed;
  const [integer, decimal] = magnitude.split(".");
  const integerOut = integer
    .replace(/\B(?=(\d{3})+(?!\d))/g, THOUSANDS_SENTINEL)
    .split(THOUSANDS_SENTINEL)
    .join(format.thousands_separator);
  const result =
    decimal !== undefined
      ? `${integerOut}${format.decimal_separator}${decimal}`
      : integerOut;
  return negative ? `-${result}` : result;
}

export function formatNumber(
  value: number | string | null | undefined,
  format: CurrencyFormat,
  options?: { decimalPlaces?: number },
): string {
  if (value === null || value === undefined || value === "") return NA;
  const numeric = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(numeric)) return NA;
  return applyFormat(numeric, format, options?.decimalPlaces);
}

export function formatCurrency(
  value: number | string | null | undefined,
  format: CurrencyFormat,
  currency?: string | null,
): string {
  const formatted = formatNumber(value, format);
  if (formatted === NA) return NA;
  return currency ? `${currency} ${formatted}` : formatted;
}

export function formatPercent(
  value: number | string | null | undefined,
  format: CurrencyFormat,
  options?: { fromFraction?: boolean; decimalPlaces?: number },
): string {
  if (value === null || value === undefined || value === "") return NA;
  const numeric = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(numeric)) return NA;
  const fromFraction = options?.fromFraction ?? false;
  const scaled = fromFraction ? numeric * 100 : numeric;
  return `${formatNumber(scaled, format, { decimalPlaces: options?.decimalPlaces ?? 1 })}%`;
}

const MILLION = 1_000_000;

/**
 * Compact-magnitude formatter for absolute-USD storage.
 *
 * Reports every absolute amount in **millions** so the unit stays
 * consistent across the app — `1,318,551,000` → `"1,318.55M"`,
 * `543,210,000` → `"543.21M"`. Per-share figures (EPS, current price)
 * are always below 1M and render with the user's currency-format
 * defaults so EPS still looks like `"0.10"` rather than `"0.00M"`.
 */
export function formatAbbreviated(
  value: number | string | null | undefined,
  format: CurrencyFormat,
  options?: { decimalPlaces?: number },
): string {
  if (value === null || value === undefined || value === "") return NA;
  const numeric = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(numeric)) return NA;

  if (Math.abs(numeric) >= MILLION) {
    return `${formatNumber(numeric / MILLION, format, {
      decimalPlaces: options?.decimalPlaces ?? 2,
    })}M`;
  }
  return formatNumber(numeric, format, options);
}
