/**
 * Historical EBIT bar chart — one bar per reported quarter, with an MA8 line.
 * EBIT is taken as operating income (the standard proxy; EBITDA = EBIT + D&A).
 * Negative quarters render below the zero baseline; large values are
 * abbreviated (e.g. 1.2B).
 */

import { useFinancials } from "@/lib/financials";

import { HistoryBarChart } from "./HistoryBarChart";

interface EbitBarChartProps {
  symbol: string;
}

export function EbitBarChart({ symbol }: EbitBarChartProps) {
  const financialsQuery = useFinancials(symbol);

  const data = (financialsQuery.data ?? [])
    .slice()
    .sort((a, b) => a.period.localeCompare(b.period))
    .map((r) => ({
      period: r.period,
      value: r.operating_income === null ? null : Number(r.operating_income),
    }));

  return (
    <HistoryBarChart
      title="EBIT"
      valueName="EBIT"
      data={data}
      isLoading={financialsQuery.isLoading}
      emptyText="No EBIT history yet."
      highlightNegative
      abbreviate
    />
  );
}
