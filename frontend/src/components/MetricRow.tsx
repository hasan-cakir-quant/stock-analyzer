import {
  useCurrencyFormat,
  useNumberFormat,
  usePercentFormat,
} from "@/lib/settings";
import { cn } from "@/lib/utils";

type MetricFormat = "number" | "currency" | "percent" | "raw";

interface MetricRowProps {
  label: string;
  value: number | string | null | undefined;
  format?: MetricFormat;
  /** Suffix appended to formatted numbers (e.g. "x", "yrs"). Ignored for `currency`. */
  unit?: string;
  /** Currency code for `format="currency"`. */
  currency?: string | null;
  /** Override the default decimal places. */
  decimalPlaces?: number;
  /** Pass true if `value` is a fraction (0.05 → 5%) for `format="percent"`. */
  fromFraction?: boolean;
  className?: string;
}

export function MetricRow({
  label,
  value,
  format = "number",
  unit,
  currency,
  decimalPlaces,
  fromFraction,
  className,
}: MetricRowProps) {
  const formatNumber = useNumberFormat();
  const formatCurrency = useCurrencyFormat();
  const formatPercent = usePercentFormat();

  let display: string;
  switch (format) {
    case "currency":
      display = formatCurrency(value, currency);
      break;
    case "percent":
      display = formatPercent(value, { fromFraction, decimalPlaces });
      break;
    case "raw":
      display = value === null || value === undefined ? "—" : String(value);
      break;
    default:
      display = formatNumber(value, { decimalPlaces });
  }

  if (unit && format !== "currency" && display !== "—") {
    display = `${display} ${unit}`;
  }

  return (
    <div className={cn("flex items-baseline justify-between gap-2 text-xs", className)}>
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium tabular-nums">{display}</span>
    </div>
  );
}
