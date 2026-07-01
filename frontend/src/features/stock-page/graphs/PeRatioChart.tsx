/**
 * Historical P/E bar chart — one bar per quarter, using the quarter-end
 * closing price over trailing-twelve-months diluted EPS (price ÷ TTM EPS).
 * Quarters without a full TTM EPS window, a price, or with non-positive
 * earnings are left blank (P/E is undefined there).
 *
 * An *isolated* missing quarter (a gap with reported EPS on both sides) is
 * linearly interpolated from its neighbors so the TTM window stays a true
 * 4-quarter sum — that one quarter is an estimate. Runs of two or more
 * consecutive missing quarters are left as gaps.
 */

import { useFinancials } from "@/lib/financials";

import { HistoryBarChart } from "./HistoryBarChart";
import { fillIsolatedGaps, trailingTtm } from "./ttm";

interface PeRatioChartProps {
  symbol: string;
}

export function PeRatioChart({ symbol }: PeRatioChartProps) {
  const financialsQuery = useFinancials(symbol);

  const rows = (financialsQuery.data ?? [])
    .slice()
    .sort((a, b) => a.period.localeCompare(b.period));

  const filledEps = fillIsolatedGaps(
    rows.map((r) => (r.eps_diluted === null ? null : Number(r.eps_diluted))),
  );

  const data = rows.map((r, i) => {
    const price = r.closing_price === null ? null : Number(r.closing_price);
    const ttmEps = trailingTtm(filledEps, i);

    const pe =
      price !== null && Number.isFinite(price) && ttmEps !== null && ttmEps > 0
        ? price / ttmEps
        : null;

    return { period: r.period, value: pe };
  });

  return (
    <HistoryBarChart
      title="P/E (TTM)"
      valueName="P/E"
      data={data}
      isLoading={financialsQuery.isLoading}
      emptyText="No P/E history yet."
    />
  );
}
