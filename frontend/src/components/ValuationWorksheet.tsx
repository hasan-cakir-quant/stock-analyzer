/**
 * Renders a `ValuationResult`'s steps list as a worksheet — the same
 * layout the inline FairValueCard popover uses, lifted into a standalone
 * component so it can also be rendered inside a Modal (used by the
 * comparison table's per-cell drill-down).
 */

import type { ValuationStep } from "@/lib/analysis";
import {
  getValuationExplainer,
  type InputFormat,
} from "@/lib/explainers";
import {
  useAbbreviatedFormat,
  useCurrencyFormat,
  useNumberFormat,
  usePercentFormat,
} from "@/lib/settings";
import { cn } from "@/lib/utils";

interface ValuationWorksheetProps {
  model: string;
  steps?: ValuationStep[];
  fairValue: number | null;
  currency?: string | null;
  computable: boolean;
  reason?: string | null;
  /** Compact strips the formula/description header — used by the modal. */
  compact?: boolean;
}

export function ValuationWorksheet({
  model,
  steps,
  fairValue,
  currency,
  computable,
  reason,
  compact = false,
}: ValuationWorksheetProps) {
  const formatCurrency = useCurrencyFormat();
  const formatPercent = usePercentFormat();
  const formatNumber = useNumberFormat();
  const formatAbbreviated = useAbbreviatedFormat();
  const explainer = getValuationExplainer(model);

  function renderValue(format: string, raw: number | null | undefined): string {
    if (raw === null || raw === undefined) return "—";
    switch (format as InputFormat) {
      case "currency":
        return formatAbbreviated(raw);
      case "percent":
        return formatPercent(raw, { fromFraction: true, decimalPlaces: 2 });
      case "percent_pct":
        return `${formatNumber(raw, { decimalPlaces: 2 })}%`;
      case "integer":
        return formatNumber(raw, { decimalPlaces: 0 });
      case "ratio":
        return `${formatNumber(raw, { decimalPlaces: 2 })}×`;
      default:
        return formatNumber(raw);
    }
  }

  // Highlight the final fair-value row so the eye finds it after scrolling.
  const lastStepIndex = steps && steps.length > 0 ? steps.length - 1 : -1;

  return (
    <div className="space-y-1.5">
      {!compact && (
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-xs font-semibold">{model}</span>
          {computable && fairValue !== null && (
            <span className="text-xs font-semibold tabular-nums">
              {formatCurrency(fairValue, currency)}
            </span>
          )}
        </div>
      )}
      {!compact && explainer && (
        <>
          <div className="rounded bg-muted/40 px-1.5 py-1 font-mono text-[10px] leading-snug">
            {explainer.formula}
          </div>
          <p className="text-[10px] leading-snug text-muted-foreground">
            {explainer.description}
          </p>
        </>
      )}
      {!computable ? (
        <p className="rounded border border-warning/30 bg-warning/10 px-1.5 py-1 text-[11px] text-warning">
          {reason ?? "Not computable with current data."}
        </p>
      ) : steps && steps.length > 0 ? (
        <div className={cn(!compact && "border-t border-border pt-1")}>
          <div className="mb-0.5 text-[9px] uppercase tracking-wide text-muted-foreground">
            Calculation worksheet
          </div>
          <ol
            className={cn(
              "space-y-1 pr-0.5",
              compact ? "max-h-[60vh] overflow-y-auto" : "max-h-72 overflow-y-auto",
            )}
          >
            {steps.map((s, i) => (
              <li
                key={i}
                className={cn(
                  "rounded px-1 py-0.5",
                  i === lastStepIndex && "bg-accent text-foreground",
                )}
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-muted-foreground">{s.label}</span>
                  <span className="font-medium tabular-nums">
                    {renderValue(s.format, s.value)}
                  </span>
                </div>
                {s.formula && (
                  <div className="font-mono text-[9px] text-muted-foreground/80">
                    {s.formula}
                  </div>
                )}
                {s.details && s.details.length > 0 && (
                  <ul className="mt-0.5 space-y-0.5 border-l border-border/60 pl-1.5">
                    {s.details.map((d, di) => (
                      <li
                        key={di}
                        className="flex items-baseline justify-between gap-2"
                      >
                        <span className="font-mono text-[10px] text-muted-foreground">
                          {d.label}
                        </span>
                        <span className="tabular-nums text-[10px]">
                          {renderValue(d.format, d.value)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </div>
  );
}
