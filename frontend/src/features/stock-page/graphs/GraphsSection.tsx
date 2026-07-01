/**
 * "Graphs" — a collapsible home for small per-stock charts. Add new graph
 * cards to the stack below as they're built; each is self-contained and
 * reads its own data.
 */

import { useState } from "react";

import { CollapsibleSection } from "@/components/CollapsibleSection";

import { BvpsBarChart } from "./BvpsBarChart";
import { EbitBarChart } from "./EbitBarChart";
import { EbitdaBarChart } from "./EbitdaBarChart";
import { EpsBarChart } from "./EpsBarChart";
import { EvEbitChart } from "./EvEbitChart";
import { EvEbitdaChart } from "./EvEbitdaChart";
import { EvFcfChart } from "./EvFcfChart";
import { FcfBarChart } from "./FcfBarChart";
import { GraphsFilterProvider, QUARTER_WINDOWS } from "./graphsFilter";
import { HistoricalValuationChart } from "./HistoricalValuationChart";
import { PbRatioChart } from "./PbRatioChart";
import { PeRatioChart } from "./PeRatioChart";
import { PsRatioChart } from "./PsRatioChart";
import { SpsBarChart } from "./SpsBarChart";

interface GraphsSectionProps {
  symbol: string;
  isFinancial?: boolean;
}

export function GraphsSection({ symbol, isFinancial = false }: GraphsSectionProps) {
  const [maxQuarters, setMaxQuarters] = useState<number | null>(null);

  return (
    <CollapsibleSection
      title="Graphs"
      trailing={
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
            Quarters
          </span>
          <div className="flex items-center gap-0.5">
            {QUARTER_WINDOWS.map((window) => {
              const active = maxQuarters === window;
              return (
                <button
                  key={window ?? "all"}
                  type="button"
                  onClick={() => setMaxQuarters(window)}
                  className={`rounded px-1.5 py-0.5 text-[10px] tabular-nums ${
                    active
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-accent hover:text-foreground"
                  }`}
                >
                  {window === null ? "All" : `${window}q`}
                </button>
              );
            })}
          </div>
        </div>
      }
    >
      <GraphsFilterProvider value={maxQuarters}>
        <div className="space-y-1.5">
          {/* Up to 4 small graphs per row. */}
          <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-4">
            <EpsBarChart symbol={symbol} />
            <PeRatioChart symbol={symbol} />
            <BvpsBarChart symbol={symbol} />
            <PbRatioChart symbol={symbol} />
            <SpsBarChart symbol={symbol} />
            <PsRatioChart symbol={symbol} />
            <EbitdaBarChart symbol={symbol} />
            <EvEbitdaChart symbol={symbol} isFinancial={isFinancial} />
            <EbitBarChart symbol={symbol} />
            <EvEbitChart symbol={symbol} isFinancial={isFinancial} />
            <FcfBarChart symbol={symbol} />
            <EvFcfChart symbol={symbol} isFinancial={isFinancial} />
          </div>

          {/* Full-width multi-line valuation overlay. */}
          <HistoricalValuationChart symbol={symbol} isFinancial={isFinancial} />
        </div>
      </GraphsFilterProvider>
    </CollapsibleSection>
  );
}
