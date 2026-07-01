/**
 * Human-readable formulas + input descriptions for each valuation model,
 * and formula descriptions for each grading metric.
 *
 * Used by hover popovers in `FairValueCard` and `GradesCard` so the user
 * can see *how* a number was computed, not just the number itself.
 */

export type InputFormat = "currency" | "percent" | "percent_pct" | "number" | "integer" | "ratio";

export interface ExplainerLine {
  key: string;
  label: string;
  format: InputFormat;
}

export interface ValuationExplainer {
  /** Short human formula, e.g. `V = sum(FCF_t / (1+r)^t) + TV / (1+r)^N`. */
  formula: string;
  /** Free-form one-paragraph description of the approach. */
  description: string;
  /** Inputs to display, in render order. */
  inputs: ExplainerLine[];
}

const VALUATION_EXPLAINERS: Record<string, ValuationExplainer> = {
  pe_based: {
    formula: "V = TTM EPS · target P/E",
    description:
      "Multiple-based fair price using a user-supplied target P/E.",
    inputs: [
      { key: "ttm_eps", label: "TTM EPS (diluted)", format: "currency" },
      { key: "target_pe", label: "Target P/E", format: "ratio" },
    ],
  },
  pb_based: {
    formula: "V = BVPS · target P/B,  BVPS = book value / shares",
    description:
      "Multiple-based fair price using book value per share (latest total equity ÷ shares) and a user-supplied target P/B. Applies to all stocks, including banks.",
    inputs: [
      { key: "book_value", label: "Book value (equity)", format: "currency" },
      { key: "book_value_per_share", label: "Book value / share", format: "currency" },
      { key: "target_pb", label: "Target P/B", format: "ratio" },
      { key: "shares_outstanding", label: "Shares outstanding", format: "currency" },
    ],
  },
  ev_ebitda: {
    formula: "EV = TTM EBITDA · target multiple,  Equity = EV − net debt",
    description:
      "EV/EBITDA multiple bridged back to equity by subtracting net debt (LTD + STD − cash).",
    inputs: [
      { key: "ttm_ebitda", label: "TTM EBITDA", format: "currency" },
      { key: "target_ev_ebitda", label: "Target EV/EBITDA", format: "ratio" },
      { key: "net_debt", label: "Net debt", format: "currency" },
      { key: "shares_outstanding", label: "Shares outstanding", format: "currency" },
    ],
  },
  ev_ebit: {
    formula: "EV = TTM EBIT · target multiple,  Equity = EV − net debt",
    description:
      "EV/EBIT multiple bridged back to equity by subtracting net debt (LTD + STD − cash). EBIT is operating income.",
    inputs: [
      { key: "ttm_ebit", label: "TTM EBIT", format: "currency" },
      { key: "target_ev_ebit", label: "Target EV/EBIT", format: "ratio" },
      { key: "net_debt", label: "Net debt", format: "currency" },
      { key: "shares_outstanding", label: "Shares outstanding", format: "currency" },
    ],
  },
  ev_fcf: {
    formula: "EV = TTM FCF · target multiple,  Equity = EV − net debt",
    description:
      "EV/FCF multiple bridged back to equity by subtracting net debt (LTD + STD − cash). Uses trailing-twelve-month free cash flow.",
    inputs: [
      { key: "ttm_fcf", label: "TTM free cash flow", format: "currency" },
      { key: "target_ev_fcf", label: "Target EV/FCF", format: "ratio" },
      { key: "net_debt", label: "Net debt", format: "currency" },
      { key: "shares_outstanding", label: "Shares outstanding", format: "currency" },
    ],
  },
};

export function getValuationExplainer(model: string): ValuationExplainer | null {
  return VALUATION_EXPLAINERS[model] ?? null;
}

// ---------------------------------------------------------------------------
// Grading metrics
// ---------------------------------------------------------------------------

export interface MetricExplainer {
  /** Short formula string. */
  formula: string;
  /** Free-form sentence on the intuition. */
  description: string;
  /** How to format the metric's raw value in the breakdown row. */
  valueFormat: InputFormat;
}

const METRIC_EXPLAINERS: Record<string, MetricExplainer> = {
  // Profitability
  roe: {
    formula: "ROE = TTM net income / latest total equity",
    description: "Return on equity — how efficiently shareholder capital generates profit.",
    valueFormat: "percent",
  },
  roa: {
    formula: "ROA = TTM net income / latest total assets",
    description: "Return on assets — how efficiently the asset base produces profit.",
    valueFormat: "percent",
  },
  roic: {
    formula: "ROIC ≈ TTM net income / (equity + LT debt + ST debt)",
    description: "Return on invested capital. Rewards companies that earn more than their cost of capital.",
    valueFormat: "percent",
  },
  net_margin: {
    formula: "Net Margin = TTM net income / TTM revenue",
    description: "Bottom-line margin after every cost.",
    valueFormat: "percent",
  },
  gross_margin: {
    formula: "Gross Margin = TTM gross profit / TTM revenue",
    description: "Margin left after direct cost of revenue.",
    valueFormat: "percent",
  },
  operating_margin: {
    formula: "Operating Margin = TTM operating income / TTM revenue",
    description: "Margin from core operations, before interest and taxes.",
    valueFormat: "percent",
  },
  // Financial Strength
  debt_to_equity: {
    formula: "D/E = (LT debt + ST debt) / total equity",
    description: "Leverage: lower is generally safer.",
    valueFormat: "ratio",
  },
  current_ratio: {
    formula: "Current Ratio = current assets / current liabilities",
    description: "Short-term liquidity. ≥ 1 means current assets cover current liabilities.",
    valueFormat: "ratio",
  },
  quick_ratio: {
    formula: "Quick = (cash + ST inv. + receivables) / current liabilities",
    description: "Liquidity excluding inventory — stricter than current ratio.",
    valueFormat: "ratio",
  },
  interest_coverage: {
    formula: "Coverage = TTM operating income / |TTM interest expense|",
    description: "How many times operating income covers interest payments.",
    valueFormat: "ratio",
  },
  debt_to_ebitda: {
    formula: "D/EBITDA = total debt / TTM EBITDA",
    description: "Years of EBITDA needed to repay debt — lower is safer.",
    valueFormat: "ratio",
  },
  // Valuation
  pe: {
    formula: "P/E = current price / TTM EPS (diluted)",
    description: "Price multiple of earnings — lower can mean cheaper.",
    valueFormat: "ratio",
  },
  pb: {
    formula: "P/B = current price / book value per share",
    description: "Price multiple of accounting book equity.",
    valueFormat: "ratio",
  },
  ps: {
    formula: "P/S = market cap / TTM revenue",
    description: "Price relative to sales.",
    valueFormat: "ratio",
  },
  ev_ebitda: {
    formula: "EV/EBITDA = (mkt cap + debt − cash) / TTM EBITDA",
    description: "Capital-structure-neutral earnings multiple.",
    valueFormat: "ratio",
  },
  peg: {
    formula: "PEG = P/E / earnings growth (in percent)",
    description: "P/E adjusted for growth. PEG < 1 is the rule of thumb for cheap.",
    valueFormat: "ratio",
  },
  // price_vs_fair_value dropped in migration 0009.
  // Growth
  revenue_growth: {
    formula: "CAGR of TTM revenue series",
    description: "Annualised revenue growth across the full history available.",
    valueFormat: "percent",
  },
  eps_growth: {
    formula: "CAGR of TTM EPS series",
    description: "Annualised earnings-per-share growth.",
    valueFormat: "percent",
  },
  fcf_growth: {
    formula: "CAGR of TTM free-cash-flow series",
    description: "Annualised free-cash-flow growth.",
    valueFormat: "percent",
  },
  book_value_growth: {
    formula: "CAGR of total equity sampled at one-year intervals",
    description: "Compounding of accounting book value over the history.",
    valueFormat: "percent",
  },
  // Efficiency
  asset_turnover: {
    formula: "Asset Turnover = TTM revenue / total assets",
    description: "How many dollars of revenue per dollar of assets.",
    valueFormat: "ratio",
  },
  inventory_turnover: {
    formula: "Inventory Turnover = TTM COGS / inventory",
    description: "How many times inventory is sold and replaced per year.",
    valueFormat: "ratio",
  },
  cash_conversion_cycle: {
    formula: "CCC = DIO + DSO  (DPO not tracked yet)",
    description: "Days from cash invested in inventory/receivables back to cash.",
    valueFormat: "ratio",
  },
  // Safety
  beta: {
    formula: "User-supplied beta from Parameter Panel",
    description: "Market sensitivity. 1 = moves with the market.",
    valueFormat: "ratio",
  },
  altman_z_score: {
    formula: "Z = 1.2A + 1.4B + 3.3C + 0.6D + E (5-factor, retained earnings approximated by equity)",
    description: "Bankruptcy-risk score. > 3 is safe, < 1.8 distressed.",
    valueFormat: "ratio",
  },
  piotroski_f_score: {
    formula: "9-point checklist on TTM vs. prior TTM",
    description: "Year-over-year fundamental improvement score. 9 is best.",
    valueFormat: "integer",
  },
  debt_levels: {
    formula: "Total debt / total assets",
    description: "Leverage normalised by asset base.",
    valueFormat: "percent",
  },
  // Dividend
  dividend_yield: {
    formula: "Yield = (TTM dividends / shares) / current price",
    description: "Cash payout as a percentage of price.",
    valueFormat: "percent",
  },
  payout_ratio: {
    formula: "Payout = |TTM dividends| / TTM net income",
    description: "Share of profits returned to shareholders.",
    valueFormat: "percent",
  },
  dividend_growth_rate: {
    formula: "CAGR of rolling-TTM dividends paid",
    description: "How fast the dividend has compounded.",
    valueFormat: "percent",
  },
  consecutive_growth_years: {
    formula: "Trailing count of years where TTM dividends grew",
    description: "Streak of consecutive year-over-year increases.",
    valueFormat: "integer",
  },
};

export function getMetricExplainer(metric: string): MetricExplainer | null {
  return METRIC_EXPLAINERS[metric] ?? null;
}
