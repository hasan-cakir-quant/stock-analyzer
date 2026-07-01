import { CollapsibleSection } from "@/components/CollapsibleSection";
import type { GrowthBlock } from "@/lib/analysis";
import { usePercentFormat } from "@/lib/settings";
import { cn } from "@/lib/utils";

interface GrowthCardProps {
  growth: GrowthBlock;
}

// Display labels + a flag distinguishing CAGR rows (e.g. "Revenue") from
// trend deltas (margins / ROE) so we can show a "Δ" hint without the
// user wondering why one row reads as a CAGR and another as a delta.
const METRIC_DEFS: Array<{ key: string; label: string; trend?: boolean }> = [
  { key: "revenue", label: "Revenue" },
  { key: "net_income", label: "Net Income" },
  { key: "ebitda", label: "EBITDA" },
  { key: "eps_diluted", label: "EPS (diluted)" },
  { key: "free_cash_flow", label: "Free Cash Flow" },
  { key: "operating_cash_flow", label: "Operating Cash Flow" },
  { key: "dividend_per_share", label: "Dividend / Share" },
  { key: "book_value_per_share", label: "Book Value / Share" },
  { key: "gross_margin_trend", label: "Gross Margin", trend: true },
  { key: "operating_margin_trend", label: "Operating Margin", trend: true },
  { key: "roe_trend", label: "ROE", trend: true },
];

export function GrowthCard({ growth }: GrowthCardProps) {
  const formatPercent = usePercentFormat();
  const horizons = growth.horizons;

  // Filter to metrics actually present in the payload — avoids dead rows
  // if the backend ever drops a row from the table.
  const rows = METRIC_DEFS.filter(({ key }) => growth.metrics[key]);

  return (
    <CollapsibleSection title="Growth">
      <div className="overflow-x-auto">
        <table className="w-full border-separate border-spacing-0 text-[11px]">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 min-w-[140px] bg-card px-2 py-1 text-left font-medium text-muted-foreground">
                Metric
              </th>
              {horizons.map((h) => (
                <th
                  key={h}
                  className="min-w-[60px] border-l border-border px-2 py-1 text-right font-medium tabular-nums"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(({ key, label, trend }) => (
              <tr key={key} className="border-t border-border">
                <th
                  scope="row"
                  className="sticky left-0 z-10 bg-card px-2 py-0.5 text-left font-medium text-foreground"
                >
                  <div className="flex items-center gap-1">
                    <span>{label}</span>
                    {trend && (
                      <span
                        title="Change in percentage points (period delta), not a CAGR."
                        className="rounded bg-muted/40 px-1 text-[8px] uppercase tracking-wide text-muted-foreground"
                      >
                        Δ
                      </span>
                    )}
                  </div>
                </th>
                {horizons.map((h) => {
                  const value = growth.metrics[key]?.[h] ?? null;
                  const positive = value !== null && value > 0;
                  const negative = value !== null && value < 0;
                  return (
                    <td
                      key={h}
                      className={cn(
                        "border-l border-t border-border px-2 py-0.5 text-right tabular-nums",
                        value === null && "text-muted-foreground/40",
                        positive && "text-success",
                        negative && "text-destructive",
                      )}
                    >
                      {value === null
                        ? "—"
                        : formatPercent(value, { fromFraction: true })}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </CollapsibleSection>
  );
}
