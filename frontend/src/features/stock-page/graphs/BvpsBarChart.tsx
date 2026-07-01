/**
 * Historical book-value-per-share bar chart — one bar per reported quarter
 * (total equity ÷ diluted shares), with an MA8/MA4/MA12 line.
 */

import { useFinancials } from "@/lib/financials";

import { HistoryBarChart } from "./HistoryBarChart";

interface BvpsBarChartProps {
  symbol: string;
}

function num(v: string | null): number | null {
  return v === null ? null : Number(v);
}

export function BvpsBarChart({ symbol }: BvpsBarChartProps) {
  const financialsQuery = useFinancials(symbol);

  const data = (financialsQuery.data ?? [])
    .slice()
    .sort((a, b) => a.period.localeCompare(b.period))
    .map((r) => {
      const equity = num(r.total_equity);
      const shares = num(r.shares_outstanding_diluted);
      return {
        period: r.period,
        value:
          equity !== null && shares !== null && shares > 0 ? equity / shares : null,
      };
    });

  return (
    <HistoryBarChart
      title="Book value / share"
      valueName="BVPS"
      data={data}
      isLoading={financialsQuery.isLoading}
      emptyText="No book-value history yet."
      highlightNegative
    />
  );
}
