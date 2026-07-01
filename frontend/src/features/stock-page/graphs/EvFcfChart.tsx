/**
 * Historical EV/FCF bar chart — one bar per quarter, using the quarter-end
 * enterprise value (market cap + net debt) over trailing-twelve-months free
 * cash flow.
 *
 *   EV       = closing price × diluted shares + (LT debt + ST debt − cash)
 *   EV/FCF   = EV ÷ TTM FCF
 *
 * Isolated single-quarter FCF gaps are interpolated so the TTM window stays a
 * true 4-quarter sum. Quarters lacking the inputs, with non-positive TTM FCF,
 * or with negative EV are left blank. Not applicable to financials.
 */

import { useFinancials } from "@/lib/financials";

import { HistoryBarChart, NotApplicableGraph } from "./HistoryBarChart";
import { fillIsolatedGaps, trailingTtm } from "./ttm";

interface EvFcfChartProps {
  symbol: string;
  isFinancial?: boolean;
}

function num(v: string | null): number | null {
  return v === null ? null : Number(v);
}

export function EvFcfChart({ symbol, isFinancial = false }: EvFcfChartProps) {
  const financialsQuery = useFinancials(symbol);

  if (isFinancial) {
    return (
      <NotApplicableGraph
        title="EV/FCF (TTM)"
        reason="Not applicable to financials — use P/E or P/B."
      />
    );
  }

  const rows = (financialsQuery.data ?? [])
    .slice()
    .sort((a, b) => a.period.localeCompare(b.period));

  const filledFcf = fillIsolatedGaps(rows.map((r) => num(r.free_cash_flow)));

  const data = rows.map((r, i) => {
    const price = num(r.closing_price);
    const shares = num(r.shares_outstanding_diluted);
    const ttmFcf = trailingTtm(filledFcf, i);

    let ev: number | null = null;
    if (price !== null && shares !== null && Number.isFinite(price) && Number.isFinite(shares)) {
      const netDebt =
        (num(r.long_term_debt) ?? 0) + (num(r.short_term_debt) ?? 0) - (num(r.cash_and_equivalents) ?? 0);
      ev = price * shares + netDebt;
    }

    // Guard negative EV (cash > market cap) — the ratio is meaningless then.
    const ratio =
      ev !== null && ev > 0 && ttmFcf !== null && ttmFcf > 0 ? ev / ttmFcf : null;

    return { period: r.period, value: ratio };
  });

  return (
    <HistoryBarChart
      title="EV/FCF (TTM)"
      valueName="EV/FCF"
      data={data}
      isLoading={financialsQuery.isLoading}
      emptyText="No EV/FCF history yet."
    />
  );
}
