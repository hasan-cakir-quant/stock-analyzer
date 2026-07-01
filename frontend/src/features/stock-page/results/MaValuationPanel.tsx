/**
 * MA-based valuation — values the stock off the latest trailing MA4 / MA8 / MA12
 * of each method's own realized multiple (P/E, P/B, EV/EBITDA, EV/EBIT, EV/FCF),
 * scaled by a scenario:
 *
 *   Pessimist → multiple × 0.80  (−20%)
 *   Normal    → multiple × 0.90  (−10%)
 *   Optimist  → multiple × 1.00  (as-is)
 *
 * Each cell is the implied fair value per share; upside is vs the latest fetched
 * price. EV-based methods are omitted for financials. All client-side, reusing
 * the realized-multiple math from the graphs.
 */

import { Camera } from "lucide-react";
import { useMemo, useState } from "react";

import { CollapsibleSection } from "@/components/CollapsibleSection";
import { useCreateSnapshot } from "@/lib/analysis";
import { useFinancials } from "@/lib/financials";
import { useParameters } from "@/lib/parameters";
import { useCurrencyFormat, usePercentFormat } from "@/lib/settings";
import { useToast } from "@/stores/toast";
import { cn } from "@/lib/utils";

import {
  computeMaMethods,
  MA_WINDOWS,
  type MaWindow,
} from "@/features/stock-page/graphs/maValuation";
import { FairValueDistributionChart } from "@/features/stock-page/graphs/FairValueDistributionChart";
import { computeValueArea } from "@/features/stock-page/graphs/valueArea";

interface MaValuationPanelProps {
  symbol: string;
  currency: string | null;
  isFinancial?: boolean;
}

const SCENARIOS = [
  { key: "super_pessimist", label: "Super pess −40%", factor: 0.6 },
  { key: "pessimist", label: "Pessimist −20%", factor: 0.8 },
  { key: "normal", label: "Normal −10%", factor: 0.9 },
  { key: "optimist", label: "Optimist", factor: 1.0 },
  { key: "super_optimist", label: "Super opt +30%", factor: 1.3 },
] as const;

type ScenarioKey = (typeof SCENARIOS)[number]["key"];

export function MaValuationPanel({ symbol, currency, isFinancial = false }: MaValuationPanelProps) {
  const financialsQuery = useFinancials(symbol);
  const parametersQuery = useParameters(symbol);
  const createSnapshot = useCreateSnapshot(symbol);
  const toast = useToast();
  const formatCurrency = useCurrencyFormat();
  const formatPercent = usePercentFormat();
  const [scenario, setScenario] = useState<ScenarioKey>("normal");

  const scenarioDef = SCENARIOS.find((s) => s.key === scenario)!;
  const factor = scenarioDef.factor;

  const methods = useMemo(() => {
    const all = computeMaMethods(financialsQuery.data ?? []);
    return all.filter((m) => !isFinancial || !m.ev);
  }, [financialsQuery.data, isFinancial]);

  const currentPrice =
    parametersQuery.data?.current_price != null
      ? Number(parametersQuery.data.current_price)
      : null;

  // Every fair-value cell of the table for the selected scenario, flattened —
  // the population the distribution chart bins. Recomputes when the scenario
  // (factor) changes.
  const scenarioFairValues = useMemo(
    () =>
      methods
        .flatMap((m) =>
          MA_WINDOWS.map((w) => {
            const rawMa = m.ma[w];
            return rawMa !== null ? m.fairValue(rawMa * factor) : null;
          }),
        )
        .filter((v): v is number => v !== null && Number.isFinite(v)),
    [methods, factor],
  );

  // Value area = central 70% of the estimates; its mean is the headline fair
  // value frozen into the snapshot (replacing the old plain average).
  const valueArea = useMemo(
    () => computeValueArea(scenarioFairValues),
    [scenarioFairValues],
  );

  async function handleSaveSnapshot() {
    // Freeze the MA-based valuation matrix at the current scenario.
    const maValuations = {
      scenario: scenario,
      scenario_label: scenarioDef.label,
      factor,
      current_price: currentPrice,
      // Central-70% value area of all fair-value cells; `value_area.mean` is
      // the snapshot's headline fair value (see backend _ma_valuations_summary).
      value_area: valueArea,
      methods: methods.map((m) => ({
        key: m.key,
        label: m.label,
        windows: MA_WINDOWS.map((w) => {
          const rawMa = m.ma[w as MaWindow];
          const multiple = rawMa !== null ? rawMa * factor : null;
          const fair = rawMa !== null ? m.fairValue(rawMa * factor) : null;
          return { window: w, multiple, fair_value: fair };
        }),
      })),
    };
    try {
      await createSnapshot.mutateAsync({
        parameters: {
          current_price: parametersQuery.data?.current_price ?? null,
          beta: parametersQuery.data?.beta ?? null,
        },
        note: `MA valuation — ${scenarioDef.label}`,
        ma_valuations: maValuations,
      });
      toast.show("Snapshot saved.", { tone: "success" });
    } catch (err) {
      toast.show(
        err instanceof Error ? `Snapshot failed — ${err.message}` : "Snapshot failed.",
        { tone: "error" },
      );
    }
  }

  return (
    <CollapsibleSection
      title="MA valuation"
      trailing={
        <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
          {SCENARIOS.map((s) => (
            <button
              key={s.key}
              type="button"
              onClick={() => setScenario(s.key)}
              className={cn(
                "rounded-md border px-2 py-0.5 text-[10px]",
                scenario === s.key
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border bg-secondary text-secondary-foreground hover:bg-accent",
              )}
            >
              {s.label}
            </button>
          ))}
          <button
            type="button"
            onClick={() => void handleSaveSnapshot()}
            disabled={createSnapshot.isPending || methods.length === 0}
            title="Freeze this MA valuation as a snapshot"
            className="ml-1 inline-flex items-center gap-1 rounded-md bg-primary px-2 py-0.5 text-[10px] font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
          >
            <Camera className="h-3 w-3" />
            {createSnapshot.isPending ? "Saving…" : "Save snapshot"}
          </button>
        </div>
      }
    >
      {financialsQuery.isLoading ? (
        <p className="text-[11px] text-muted-foreground">Loading…</p>
      ) : methods.length === 0 ? (
        <p className="text-[11px] text-muted-foreground">
          No financial history yet — import financials and fetch prices first.
        </p>
      ) : (
        <>
          <p className="mb-1.5 text-[10px] text-muted-foreground">
            Fair value = (latest MA of the realized multiple × {Math.round(factor * 100)}%) ×
            current fundamentals.{" "}
            {currentPrice !== null
              ? `Upside vs current price ${formatCurrency(currentPrice, currency)}.`
              : "Set a current price (Fetch all) to see upside."}
          </p>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-[11px]">
              <thead>
                <tr className="border-b border-border text-muted-foreground">
                  <th className="px-1.5 py-1 text-left font-medium">Method</th>
                  {MA_WINDOWS.map((w) => (
                    <th key={w} className="px-1.5 py-1 text-right font-medium">
                      MA{w}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {methods.map((m) => (
                  <tr key={m.key} className="border-b border-border/30">
                    <td className="px-1.5 py-1 font-medium">{m.label}</td>
                    {MA_WINDOWS.map((w) => {
                      const rawMa = m.ma[w as MaWindow];
                      const fair =
                        rawMa !== null ? m.fairValue(rawMa * factor) : null;
                      const upside =
                        fair !== null && currentPrice !== null && currentPrice > 0
                          ? ((fair - currentPrice) / currentPrice) * 100
                          : null;
                      return (
                        <td key={w} className="px-1.5 py-1 text-right align-top tabular-nums">
                          {fair === null ? (
                            <span className="text-muted-foreground">—</span>
                          ) : (
                            <div className="flex flex-col items-end">
                              <span className="font-medium">
                                {formatCurrency(fair, currency)}
                              </span>
                              {upside !== null && (
                                <span
                                  className={cn(
                                    "text-[10px]",
                                    upside > 0 && "text-success",
                                    upside < 0 && "text-destructive",
                                  )}
                                >
                                  {formatPercent(upside)}
                                </span>
                              )}
                              <span
                                className="text-[9px] text-muted-foreground"
                                title="Scenario-scaled multiple applied"
                              >
                                ×{(rawMa! * factor).toFixed(1)}
                              </span>
                            </div>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-2">
            <FairValueDistributionChart
              values={scenarioFairValues}
              valueArea={valueArea}
              currentPrice={currentPrice}
              currency={currency}
              scenarioLabel={scenarioDef.label}
            />
          </div>
        </>
      )}
    </CollapsibleSection>
  );
}
