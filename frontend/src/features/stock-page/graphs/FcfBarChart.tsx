/**
 * Historical free-cash-flow bar chart — one bar per reported quarter, with an
 * MA line. Negative quarters render below the zero baseline; large values are
 * abbreviated (e.g. 1.2B).
 */

import { useFinancials } from "@/lib/financials";

import { HistoryBarChart } from "./HistoryBarChart";

interface FcfBarChartProps {
  symbol: string;
}

export function FcfBarChart({ symbol }: FcfBarChartProps) {
  const financialsQuery = useFinancials(symbol);

  const data = (financialsQuery.data ?? [])
    .slice()
    .sort((a, b) => a.period.localeCompare(b.period))
    .map((r) => ({
      period: r.period,
      value: r.free_cash_flow === null ? null : Number(r.free_cash_flow),
    }));

  return (
    <HistoryBarChart
      title="Free cash flow"
      valueName="FCF"
      data={data}
      isLoading={financialsQuery.isLoading}
      emptyText="No FCF history yet."
      highlightNegative
      abbreviate
    />
  );
}
