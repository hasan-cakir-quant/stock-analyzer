/**
 * Historical EPS bar chart — one bar per reported quarter (diluted EPS),
 * with a trend line. Negative quarters render below the zero baseline.
 */

import { useFinancials } from "@/lib/financials";

import { HistoryBarChart } from "./HistoryBarChart";

interface EpsBarChartProps {
  symbol: string;
}

export function EpsBarChart({ symbol }: EpsBarChartProps) {
  const financialsQuery = useFinancials(symbol);

  const data = (financialsQuery.data ?? [])
    .slice()
    .sort((a, b) => a.period.localeCompare(b.period))
    .map((r) => ({
      period: r.period,
      value: r.eps_diluted === null ? null : Number(r.eps_diluted),
    }));

  return (
    <HistoryBarChart
      title="EPS (diluted)"
      valueName="EPS"
      data={data}
      isLoading={financialsQuery.isLoading}
      emptyText="No EPS history yet."
      highlightNegative
    />
  );
}
