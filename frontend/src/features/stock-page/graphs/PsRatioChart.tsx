/**
 * Historical P/S bar chart — one bar per quarter, using the quarter-end
 * market cap over trailing-twelve-months revenue:
 *
 *   P/S = (closing price × diluted shares) ÷ TTM revenue
 *
 * Revenue is a flow, so a 4-quarter TTM window is used (same treatment as
 * P/E with TTM EPS). An *isolated* missing quarter (a gap with reported
 * revenue on both sides) is linearly interpolated so the TTM window stays a
 * true 4-quarter sum. Quarters without a full TTM window, a price, shares,
 * or with non-positive revenue are left blank.
 */

import { useFinancials } from "@/lib/financials";

import { HistoryBarChart } from "./HistoryBarChart";
import { fillIsolatedGaps, trailingTtm } from "./ttm";

interface PsRatioChartProps {
  symbol: string;
}

function num(v: string | null): number | null {
  return v === null ? null : Number(v);
}

export function PsRatioChart({ symbol }: PsRatioChartProps) {
  const financialsQuery = useFinancials(symbol);

  const rows = (financialsQuery.data ?? [])
    .slice()
    .sort((a, b) => a.period.localeCompare(b.period));

  const filledRevenue = fillIsolatedGaps(rows.map((r) => num(r.revenue)));

  const data = rows.map((r, i) => {
    const price = num(r.closing_price);
    const shares = num(r.shares_outstanding_diluted);
    const ttmRevenue = trailingTtm(filledRevenue, i);

    const marketCap =
      price !== null && Number.isFinite(price) && shares !== null && shares > 0
        ? price * shares
        : null;
    const ps =
      marketCap !== null && ttmRevenue !== null && ttmRevenue > 0
        ? marketCap / ttmRevenue
        : null;

    return { period: r.period, value: ps };
  });

  return (
    <HistoryBarChart
      title="P/S (TTM)"
      valueName="P/S"
      data={data}
      isLoading={financialsQuery.isLoading}
      emptyText="No P/S history yet."
    />
  );
}
