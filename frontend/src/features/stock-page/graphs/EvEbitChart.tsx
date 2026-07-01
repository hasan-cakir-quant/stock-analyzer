/**
 * Historical EV/EBIT bar chart — one bar per quarter, using the quarter-end
 * enterprise value (market cap + net debt) over trailing-twelve-months EBIT
 * (operating income).
 *
 *   EV        = closing price × diluted shares + (LT debt + ST debt − cash)
 *   EV/EBIT   = EV ÷ TTM EBIT
 *
 * Isolated single-quarter EBIT gaps are interpolated so the TTM window stays a
 * true 4-quarter sum. Quarters lacking the inputs, or with non-positive TTM
 * EBIT, are left blank.
 */

import { useFinancials } from "@/lib/financials";

import { HistoryBarChart, NotApplicableGraph } from "./HistoryBarChart";
import { fillIsolatedGaps, trailingTtm } from "./ttm";

interface EvEbitChartProps {
  symbol: string;
  isFinancial?: boolean;
}

function num(v: string | null): number | null {
  return v === null ? null : Number(v);
}

export function EvEbitChart({ symbol, isFinancial = false }: EvEbitChartProps) {
  const financialsQuery = useFinancials(symbol);

  if (isFinancial) {
    return (
      <NotApplicableGraph
        title="EV/EBIT (TTM)"
        reason="Not applicable to financials — use P/E or P/B."
      />
    );
  }

  const rows = (financialsQuery.data ?? [])
    .slice()
    .sort((a, b) => a.period.localeCompare(b.period));

  const filledEbit = fillIsolatedGaps(rows.map((r) => num(r.operating_income)));

  const data = rows.map((r, i) => {
    const price = num(r.closing_price);
    const shares = num(r.shares_outstanding_diluted);
    const ttmEbit = trailingTtm(filledEbit, i);

    let ev: number | null = null;
    if (price !== null && shares !== null && Number.isFinite(price) && Number.isFinite(shares)) {
      const netDebt =
        (num(r.long_term_debt) ?? 0) + (num(r.short_term_debt) ?? 0) - (num(r.cash_and_equivalents) ?? 0);
      ev = price * shares + netDebt;
    }

    // Guard negative EV (cash > market cap) — the ratio is meaningless then.
    const ratio =
      ev !== null && ev > 0 && ttmEbit !== null && ttmEbit > 0 ? ev / ttmEbit : null;

    return { period: r.period, value: ratio };
  });

  return (
    <HistoryBarChart
      title="EV/EBIT (TTM)"
      valueName="EV/EBIT"
      data={data}
      isLoading={financialsQuery.isLoading}
      emptyText="No EV/EBIT history yet."
    />
  );
}
