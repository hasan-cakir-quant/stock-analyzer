/**
 * Historical EBITDA bar chart — one bar per reported quarter, with an MA8
 * line. Negative quarters render below the zero baseline; large values are
 * abbreviated (e.g. 1.2B).
 */

import { useFinancials } from "@/lib/financials";

import { HistoryBarChart } from "./HistoryBarChart";

interface EbitdaBarChartProps {
  symbol: string;
}

export function EbitdaBarChart({ symbol }: EbitdaBarChartProps) {
  const financialsQuery = useFinancials(symbol);

  const data = (financialsQuery.data ?? [])
    .slice()
    .sort((a, b) => a.period.localeCompare(b.period))
    .map((r) => ({
      period: r.period,
      value: r.ebitda === null ? null : Number(r.ebitda),
    }));

  return (
    <HistoryBarChart
      title="EBITDA"
      valueName="EBITDA"
      data={data}
      isLoading={financialsQuery.isLoading}
      emptyText="No EBITDA history yet."
      highlightNegative
      abbreviate
    />
  );
}
