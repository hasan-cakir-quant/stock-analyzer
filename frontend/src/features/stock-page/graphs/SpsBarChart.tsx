/**
 * Historical sales-per-share bar chart — one bar per reported quarter
 * (revenue ÷ diluted shares), with an MA4/MA8/MA12 line. Mirrors the EPS
 * chart: each bar is that single quarter's revenue per share, not a TTM sum.
 */

import { useFinancials } from "@/lib/financials";

import { HistoryBarChart } from "./HistoryBarChart";

interface SpsBarChartProps {
  symbol: string;
}

function num(v: string | null): number | null {
  return v === null ? null : Number(v);
}

export function SpsBarChart({ symbol }: SpsBarChartProps) {
  const financialsQuery = useFinancials(symbol);

  const data = (financialsQuery.data ?? [])
    .slice()
    .sort((a, b) => a.period.localeCompare(b.period))
    .map((r) => {
      const revenue = num(r.revenue);
      const shares = num(r.shares_outstanding_diluted);
      return {
        period: r.period,
        value:
          revenue !== null && shares !== null && shares > 0 ? revenue / shares : null,
      };
    });

  return (
    <HistoryBarChart
      title="Sales / share"
      valueName="SPS"
      data={data}
      isLoading={financialsQuery.isLoading}
      emptyText="No sales history yet."
      highlightNegative
    />
  );
}
