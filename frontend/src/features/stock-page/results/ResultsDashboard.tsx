/**
 * Results Dashboard (Task 21).
 *
 * Reads the latest Run-Full-Analysis result from the Zustand store
 * (Task 20 wrote it there) and renders three cards: Valuations,
 * Grades, Growth. Empty state when nothing has been run yet.
 */

import { CollapsibleSection } from "@/components/CollapsibleSection";
import { useAnalysisResult } from "@/stores/analysis";

import { GradesCard } from "./GradesCard";
import { GrowthCard } from "./GrowthCard";
import { ValuationsCard } from "./ValuationsCard";

interface ResultsDashboardProps {
  symbol: string;
  currency: string | null;
}

export function ResultsDashboard({ symbol, currency }: ResultsDashboardProps) {
  const result = useAnalysisResult(symbol);

  if (!result) {
    return (
      <CollapsibleSection title="Results Dashboard">
        <p className="text-xs text-muted-foreground">
          Click <span className="font-medium text-foreground">Run Full Analysis</span>{" "}
          in the Parameter Panel above to populate this dashboard.
        </p>
      </CollapsibleSection>
    );
  }

  return (
    <div className="space-y-2">
      <ValuationsCard valuations={result.valuations} currency={currency} />
      <GradesCard grades={result.grades} />
      <GrowthCard growth={result.growth} />
    </div>
  );
}
