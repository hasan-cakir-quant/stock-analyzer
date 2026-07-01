import { ArrowDown, ArrowUp, Info, Minus } from "lucide-react";

import { HoverPopover } from "@/components/HoverPopover";
import type { ValuationStep } from "@/lib/analysis";
import {
  getValuationExplainer,
  type InputFormat,
  type ValuationExplainer,
} from "@/lib/explainers";
import {
  useAbbreviatedFormat,
  useCurrencyFormat,
  useNumberFormat,
  usePercentFormat,
} from "@/lib/settings";
import { cn } from "@/lib/utils";

interface FairValueCardProps {
  model: string;
  fairValue: number | string | null | undefined;
  currentPrice: number | string | null | undefined;
  computable: boolean;
  reason?: string | null;
  steps?: ValuationStep[];
  currency?: string | null;
  className?: string;
}

const MODEL_LABELS: Record<string, string> = {
  dcf: "DCF",
  ddm: "DDM",
  graham_number: "Graham №",
  graham_revised: "Graham Revised",
  pe_based: "P/E Based",
  ev_ebitda: "EV/EBITDA",
  residual_income: "Residual Income",
  peter_lynch: "Peter Lynch",
};

function asNumber(v: number | string | null | undefined): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "string" ? Number(v) : v;
  return Number.isFinite(n) ? n : null;
}

export function FairValueCard({
  model,
  fairValue,
  currentPrice,
  computable,
  reason,
  steps,
  currency,
  className,
}: FairValueCardProps) {
  const formatCurrency = useCurrencyFormat();
  const formatPercent = usePercentFormat();

  const fv = asNumber(fairValue);
  const cp = asNumber(currentPrice);
  const upsidePct = fv !== null && cp !== null && cp > 0 ? ((fv - cp) / cp) * 100 : null;

  const undervalued = upsidePct !== null && upsidePct > 0;
  const overvalued = upsidePct !== null && upsidePct < 0;

  const explainer = getValuationExplainer(model);

  return (
    <div
      className={cn(
        "rounded-md border border-border bg-card p-2 text-xs shadow-sm",
        className,
      )}
    >
      <div className="flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
          {MODEL_LABELS[model] ?? model}
        </span>
        <div className="flex items-center gap-1">
          {!computable && (
            <span
              title={reason ?? "Not computable"}
              className="rounded bg-muted/40 px-1 py-0.5 text-[9px] uppercase tracking-wide text-muted-foreground"
            >
              N/A
            </span>
          )}
          {explainer && (
            <HoverPopover
              placement="top-right"
              panelClassName="w-80"
              content={
                <ExplainerPanel
                  modelLabel={MODEL_LABELS[model] ?? model}
                  explainer={explainer}
                  steps={steps}
                  fairValue={fv}
                  currency={currency}
                  computable={computable}
                  reason={reason}
                />
              }
            >
              <button
                type="button"
                aria-label="Show calculation steps"
                className="rounded p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <Info className="h-3 w-3" />
              </button>
            </HoverPopover>
          )}
        </div>
      </div>

      {computable && fv !== null ? (
        <div className="mt-0.5 text-base font-semibold tabular-nums leading-tight">
          {formatCurrency(fv, currency)}
        </div>
      ) : (
        <div
          className="mt-0.5 text-[11px] text-muted-foreground"
          title={reason ?? undefined}
        >
          {reason ?? "Not computable"}
        </div>
      )}

      <div className="mt-1 flex items-center justify-between text-[11px] text-muted-foreground tabular-nums">
        <span>vs {formatCurrency(cp, currency)}</span>
        {upsidePct !== null && (
          <span
            className={cn(
              "inline-flex items-center gap-0.5 font-medium",
              undervalued && "text-success",
              overvalued && "text-destructive",
            )}
          >
            {undervalued && <ArrowUp className="h-3 w-3" />}
            {overvalued && <ArrowDown className="h-3 w-3" />}
            {!undervalued && !overvalued && <Minus className="h-3 w-3" />}
            {formatPercent(upsidePct)}
          </span>
        )}
      </div>
    </div>
  );
}

interface ExplainerPanelProps {
  modelLabel: string;
  explainer: ValuationExplainer;
  steps?: ValuationStep[];
  fairValue: number | null;
  currency?: string | null;
  computable: boolean;
  reason?: string | null;
}

function ExplainerPanel({
  modelLabel,
  explainer,
  steps,
  fairValue,
  currency,
  computable,
  reason,
}: ExplainerPanelProps) {
  const formatCurrency = useCurrencyFormat();
  const formatPercent = usePercentFormat();
  const formatNumber = useNumberFormat();
  const formatAbbreviated = useAbbreviatedFormat();

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

  // Highlight the final fair-value-per-share row so the eye finds the
  // headline number even after scrolling through the per-year worksheet.
  const lastStepIndex = steps && steps.length > 0 ? steps.length - 1 : -1;

  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs font-semibold">{modelLabel}</span>
        {computable && fairValue !== null && (
          <span className="text-xs font-semibold tabular-nums">
            {formatCurrency(fairValue, currency)}
          </span>
        )}
      </div>
      <div className="rounded bg-muted/40 px-1.5 py-1 font-mono text-[10px] leading-snug">
        {explainer.formula}
      </div>
      <p className="text-[10px] leading-snug text-muted-foreground">
        {explainer.description}
      </p>
      {!computable ? (
        <p className="rounded border border-warning/30 bg-warning/10 px-1.5 py-1 text-[10px] text-warning">
          {reason ?? "Not computable with current data."}
        </p>
      ) : steps && steps.length > 0 ? (
        <div className="border-t border-border pt-1">
          <div className="mb-0.5 text-[9px] uppercase tracking-wide text-muted-foreground">
            Calculation worksheet
          </div>
          <ol className="max-h-72 space-y-1 overflow-y-auto pr-0.5">
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
