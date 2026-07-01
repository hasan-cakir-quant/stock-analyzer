import { CollapsibleSection } from "@/components/CollapsibleSection";
import { FairValueCard } from "@/components/FairValueCard";
import { MetricRow } from "@/components/MetricRow";
import type { ValuationsBlock } from "@/lib/analysis";

interface ValuationsCardProps {
  valuations: ValuationsBlock;
  currency: string | null;
}

// Display order — matches the order the user expects to scan in the dashboard.
const MODEL_ORDER = [
  "dcf",
  "ddm",
  "graham_number",
  "graham_revised",
  "pe_based",
  "ev_ebitda",
  "residual_income",
  "peter_lynch",
] as const;

export function ValuationsCard({ valuations, currency }: ValuationsCardProps) {
  const { models, summary } = valuations;
  const modelEntries = MODEL_ORDER.filter((name) => models[name] !== undefined);

  return (
    <CollapsibleSection title="Valuations">
      <div className="space-y-2">
        <SummaryStrip summary={summary} currency={currency} />

        <div className="grid gap-1.5 sm:grid-cols-2 2xl:grid-cols-3">
          {modelEntries.map((name) => {
            const model = models[name];
            return (
              <FairValueCard
                key={name}
                model={name}
                fairValue={model.fair_value}
                currentPrice={summary.current_price}
                computable={model.computable}
                reason={model.reason}
                steps={model.steps}
                currency={currency}
              />
            );
          })}
        </div>
      </div>
    </CollapsibleSection>
  );
}

function SummaryStrip({
  summary,
  currency,
}: {
  summary: ValuationsBlock["summary"];
  currency: string | null;
}) {
  return (
    <div className="grid gap-1 rounded-md border border-border bg-card/60 px-2 py-1.5 sm:grid-cols-4">
      <MetricRow
        label="Average fair value"
        value={summary.average}
        format="currency"
        currency={currency}
      />
      <MetricRow
        label="Median fair value"
        value={summary.median}
        format="currency"
        currency={currency}
      />
      <MetricRow
        label="Current price"
        value={summary.current_price}
        format="currency"
        currency={currency}
      />
      <MetricRow
        label="Upside / Downside"
        value={summary.upside_pct}
        format="percent"
      />
    </div>
  );
}
