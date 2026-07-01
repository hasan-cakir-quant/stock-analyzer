import { type FinancialField, type FinancialRow } from "@/lib/financials";

export interface FieldDef {
  key: FinancialField;
  label: string;
  /**
   * Inputs whose presence allows the server (and the UI) to derive this
   * field. When set + the cell is empty, the grid shows the computed
   * value in italics with a "derived" tooltip.
   */
  derivedFrom?: FinancialField[];
  derive?: (
    row: Pick<FinancialRow, FinancialField>,
    ctx?: DeriveContext,
  ) => number | null;
}

export type TabId = "income" | "balance" | "cashflow" | "market";

export interface TabDef {
  id: TabId;
  label: string;
  fields: FieldDef[];
}

export interface DeriveContext {
  /** Stock-level shares outstanding — fallback when per-quarter shares are missing. */
  stockSharesOutstanding?: number | null;
}

function deriveSubtraction(a: FinancialField, b: FinancialField) {
  return (row: Pick<FinancialRow, FinancialField>) => {
    const aValue = row[a];
    const bValue = row[b];
    if (aValue === null || bValue === null) return null;
    const an = Number(aValue);
    const bn = Number(bValue);
    if (!Number.isFinite(an) || !Number.isFinite(bn)) return null;
    return an - bn;
  };
}

function deriveEpsDiluted(
  row: Pick<FinancialRow, FinancialField>,
  ctx?: DeriveContext,
) {
  if (row.net_income === null) return null;
  const ni = Number(row.net_income);
  if (!Number.isFinite(ni)) return null;
  const perQuarter =
    row.shares_outstanding_diluted !== null
      ? Number(row.shares_outstanding_diluted)
      : null;
  const fallback = ctx?.stockSharesOutstanding ?? null;
  const shares = perQuarter ?? (fallback !== null ? Number(fallback) : null);
  if (shares === null || !Number.isFinite(shares) || shares <= 0) return null;
  return ni / shares;
}

export const TABS: TabDef[] = [
  {
    id: "income",
    label: "Income Statement",
    fields: [
      { key: "revenue", label: "Revenue" },
      { key: "cogs", label: "COGS" },
      {
        key: "gross_profit",
        label: "Gross Profit",
        derivedFrom: ["revenue", "cogs"],
        derive: deriveSubtraction("revenue", "cogs"),
      },
      { key: "operating_expenses", label: "Operating Expenses" },
      { key: "operating_income", label: "Operating Income (EBIT)" },
      { key: "interest_expense", label: "Interest Expense" },
      { key: "pretax_income", label: "Pre-tax Income" },
      { key: "net_income", label: "Net Income" },
      { key: "eps_basic", label: "EPS (basic)" },
      {
        key: "eps_diluted",
        label: "EPS (diluted)",
        derivedFrom: ["net_income", "shares_outstanding_diluted"],
        derive: deriveEpsDiluted,
      },
      { key: "ebitda", label: "EBITDA" },
      { key: "shares_outstanding_diluted", label: "Shares Outstanding (diluted)" },
    ],
  },
  {
    id: "balance",
    label: "Balance Sheet",
    fields: [
      { key: "cash_and_equivalents", label: "Cash & Equivalents" },
      { key: "short_term_investments", label: "Short-term Investments" },
      { key: "total_current_assets", label: "Total Current Assets" },
      { key: "total_assets", label: "Total Assets" },
      { key: "short_term_debt", label: "Short-term Debt" },
      { key: "total_current_liabilities", label: "Total Current Liabilities" },
      { key: "long_term_debt", label: "Long-term Debt" },
      { key: "total_liabilities", label: "Total Liabilities" },
      { key: "total_equity", label: "Total Equity" },
      { key: "inventory", label: "Inventory" },
      { key: "receivables", label: "Receivables" },
    ],
  },
  {
    id: "cashflow",
    label: "Cash Flow",
    fields: [
      { key: "operating_cash_flow", label: "Operating Cash Flow" },
      { key: "capex", label: "CapEx" },
      {
        key: "free_cash_flow",
        label: "Free Cash Flow",
        derivedFrom: ["operating_cash_flow", "capex"],
        derive: deriveSubtraction("operating_cash_flow", "capex"),
      },
      { key: "dividends_paid", label: "Dividends Paid" },
      { key: "stock_buybacks", label: "Stock Buybacks" },
    ],
  },
  {
    id: "market",
    label: "Market Data",
    fields: [{ key: "closing_price", label: "Closing Price (EoQ)" }],
  },
];
