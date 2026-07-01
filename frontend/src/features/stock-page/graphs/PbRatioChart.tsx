/**
 * Historical P/B bar chart — one bar per quarter, using the quarter-end
 * closing price over book value per share (price ÷ BVPS). Book value is a
 * point-in-time snapshot, so no trailing-twelve-month window is needed.
 * Quarters lacking a price, equity, or with non-positive book value are blank.
 */

import { useFinancials } from "@/lib/financials";

import { HistoryBarChart } from "./HistoryBarChart";

interface PbRatioChartProps {
  symbol: string;
}

function num(v: string | null): number | null {
  return v === null ? null : Number(v);
}

export function PbRatioChart({ symbol }: PbRatioChartProps) {
  const financialsQuery = useFinancials(symbol);

  const data = (financialsQuery.data ?? [])
    .slice()
    .sort((a, b) => a.period.localeCompare(b.period))
    .map((r) => {
      const price = num(r.closing_price);
      const equity = num(r.total_equity);
      const shares = num(r.shares_outstanding_diluted);
      const bvps =
        equity !== null && shares !== null && shares > 0 ? equity / shares : null;
      const pb =
        price !== null && Number.isFinite(price) && bvps !== null && bvps > 0
          ? price / bvps
          : null;
      return { period: r.period, value: pb };
    });

  return (
    <HistoryBarChart
      title="P/B"
      valueName="P/B"
      data={data}
      isLoading={financialsQuery.isLoading}
      emptyText="No P/B history yet."
    />
  );
}
