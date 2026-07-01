/**
 * Mirror of the backend seed (alembic 0002_seed_settings).
 *
 * Used by the Settings page to power "reset to default" actions and the
 * "matches default" indicator. Keep in sync if the seed migration changes.
 */

export const DEFAULT_GENERAL_GRADE_WEIGHTS: Record<string, number> = {
  profitability: 20,
  valuation: 20,
  financial_strength: 15,
  growth: 15,
  efficiency: 10,
  safety: 10,
  dividend: 10,
};

export const DEFAULT_SUB_GRADE_WEIGHTS: Record<string, Record<string, number>> = {
  profitability: {
    roe: 20,
    roa: 15,
    roic: 20,
    net_margin: 15,
    gross_margin: 15,
    operating_margin: 15,
  },
  financial_strength: {
    debt_to_equity: 25,
    current_ratio: 15,
    quick_ratio: 15,
    interest_coverage: 25,
    debt_to_ebitda: 20,
  },
  valuation: {
    // price_vs_fair_value removed in migration 0009 — pro-rata rescaled to 100.
    pe: 25,
    pb: 18.75,
    ps: 12.5,
    ev_ebitda: 25,
    peg: 18.75,
  },
  growth: {
    revenue_growth: 30,
    eps_growth: 30,
    fcf_growth: 25,
    book_value_growth: 15,
  },
  efficiency: {
    asset_turnover: 35,
    inventory_turnover: 30,
    cash_conversion_cycle: 35,
  },
  safety: {
    beta: 20,
    altman_z_score: 30,
    piotroski_f_score: 30,
    debt_levels: 20,
  },
  dividend: {
    dividend_yield: 30,
    payout_ratio: 20,
    dividend_growth_rate: 25,
    consecutive_growth_years: 25,
  },
};

// `boundary` is read as a lower bound for higher_better metrics and an
// upper bound for lower_better. `null` boundary = catch-all (always last).
export type ThresholdRange = [number | null, number];

export interface ThresholdSpec {
  direction: "higher_better" | "lower_better";
  ranges: ThresholdRange[];
}

const hb = (...ranges: ThresholdRange[]): ThresholdSpec => ({
  direction: "higher_better",
  ranges,
});
const lb = (...ranges: ThresholdRange[]): ThresholdSpec => ({
  direction: "lower_better",
  ranges,
});

export const DEFAULT_GRADE_THRESHOLDS: Record<string, ThresholdSpec> = {
  // Profitability
  roe: hb([0.25, 100], [0.2, 85], [0.15, 70], [0.1, 55], [0.05, 35], [null, 10]),
  roa: hb([0.15, 100], [0.1, 85], [0.07, 70], [0.04, 55], [0.02, 35], [null, 10]),
  roic: hb([0.2, 100], [0.15, 85], [0.1, 70], [0.07, 55], [0.04, 35], [null, 10]),
  net_margin: hb([0.2, 100], [0.15, 85], [0.1, 70], [0.05, 55], [0.02, 35], [null, 10]),
  gross_margin: hb([0.5, 100], [0.4, 85], [0.3, 70], [0.2, 55], [0.1, 35], [null, 10]),
  operating_margin: hb([0.25, 100], [0.18, 85], [0.12, 70], [0.07, 55], [0.03, 35], [null, 10]),
  // Financial Strength
  debt_to_equity: lb([0.3, 100], [0.5, 85], [1.0, 70], [1.5, 55], [2.0, 35], [null, 10]),
  current_ratio: hb([2.0, 100], [1.5, 85], [1.2, 70], [1.0, 55], [0.8, 35], [null, 10]),
  quick_ratio: hb([1.5, 100], [1.0, 85], [0.8, 70], [0.6, 55], [0.4, 35], [null, 10]),
  interest_coverage: hb([15, 100], [10, 85], [5, 70], [3, 55], [1.5, 35], [null, 10]),
  debt_to_ebitda: lb([1, 100], [2, 85], [3, 70], [4, 55], [5, 35], [null, 10]),
  // Valuation
  pe: lb([10, 100], [15, 85], [20, 70], [25, 55], [35, 35], [null, 10]),
  pb: lb([1, 100], [2, 85], [3, 70], [4, 55], [6, 35], [null, 10]),
  ps: lb([1, 100], [2, 85], [3, 70], [5, 55], [8, 35], [null, 10]),
  ev_ebitda: lb([8, 100], [12, 85], [16, 70], [20, 55], [25, 35], [null, 10]),
  peg: lb([1.0, 100], [1.5, 85], [2.0, 70], [2.5, 55], [3.0, 35], [null, 10]),
  // price_vs_fair_value dropped in migration 0009 — see metrics.py.
  // Growth
  revenue_growth: hb([0.2, 100], [0.12, 85], [0.07, 70], [0.03, 55], [0, 35], [null, 10]),
  eps_growth: hb([0.2, 100], [0.12, 85], [0.07, 70], [0.03, 55], [0, 35], [null, 10]),
  fcf_growth: hb([0.15, 100], [0.1, 85], [0.05, 70], [0.02, 55], [0, 35], [null, 10]),
  book_value_growth: hb([0.15, 100], [0.1, 85], [0.06, 70], [0.03, 55], [0, 35], [null, 10]),
  // Efficiency
  asset_turnover: hb([1.0, 100], [0.7, 85], [0.5, 70], [0.3, 55], [0.15, 35], [null, 10]),
  inventory_turnover: hb([10, 100], [6, 85], [4, 70], [2.5, 55], [1.5, 35], [null, 10]),
  cash_conversion_cycle: lb([30, 100], [60, 85], [90, 70], [120, 55], [180, 35], [null, 10]),
  // Safety
  beta: lb([0.7, 100], [1.0, 85], [1.3, 70], [1.6, 55], [2.0, 35], [null, 10]),
  altman_z_score: hb([3.0, 100], [2.6, 85], [1.8, 70], [1.0, 55], [null, 15]),
  piotroski_f_score: hb([8, 100], [7, 85], [6, 70], [5, 55], [3, 35], [null, 15]),
  debt_levels: lb([0.2, 100], [0.35, 85], [0.5, 70], [0.65, 55], [0.8, 35], [null, 10]),
  // Dividend
  dividend_yield: hb([0.05, 100], [0.04, 85], [0.03, 70], [0.02, 55], [0.01, 35], [null, 15]),
  payout_ratio: lb([0.4, 100], [0.55, 85], [0.7, 70], [0.85, 55], [1.0, 35], [null, 10]),
  dividend_growth_rate: hb([0.1, 100], [0.07, 85], [0.04, 70], [0.02, 55], [0, 35], [null, 15]),
  consecutive_growth_years: hb([20, 100], [10, 85], [5, 70], [3, 55], [1, 35], [null, 10]),
};

export const DEFAULT_CURRENCY_FORMAT = {
  thousands_separator: ",",
  decimal_separator: ".",
  decimal_places: 2,
};

export const DEFAULT_GLOBAL_MARKET_ASSUMPTIONS: Record<string, number> = {
  target_pe: 18,
  target_pb: 1.5,
  target_ev_ebitda: 12,
  target_ev_ebit: 14,
  target_ev_fcf: 18,
};

/** Pretty labels for each sub-grade and metric — used in headings/legends. */
export const SUB_GRADE_LABELS: Record<string, string> = {
  profitability: "Profitability",
  valuation: "Valuation",
  financial_strength: "Financial Strength",
  growth: "Growth",
  efficiency: "Efficiency",
  safety: "Safety",
  dividend: "Dividend",
};

export const METRIC_LABELS: Record<string, string> = {
  roe: "ROE",
  roa: "ROA",
  roic: "ROIC",
  net_margin: "Net Margin",
  gross_margin: "Gross Margin",
  operating_margin: "Operating Margin",
  debt_to_equity: "Debt / Equity",
  current_ratio: "Current Ratio",
  quick_ratio: "Quick Ratio",
  interest_coverage: "Interest Coverage",
  debt_to_ebitda: "Debt / EBITDA",
  pe: "P/E",
  pb: "P/B",
  ps: "P/S",
  ev_ebitda: "EV / EBITDA",
  peg: "PEG",
  revenue_growth: "Revenue Growth",
  eps_growth: "EPS Growth",
  fcf_growth: "FCF Growth",
  book_value_growth: "Book Value Growth",
  asset_turnover: "Asset Turnover",
  inventory_turnover: "Inventory Turnover",
  cash_conversion_cycle: "Cash Conversion Cycle",
  beta: "Beta",
  altman_z_score: "Altman Z-Score",
  piotroski_f_score: "Piotroski F-Score",
  debt_levels: "Debt Levels (D/A)",
  dividend_yield: "Dividend Yield",
  payout_ratio: "Payout Ratio",
  dividend_growth_rate: "Dividend Growth Rate",
  consecutive_growth_years: "Consecutive Growth Years",
};

export const ASSUMPTION_LABELS: Record<string, string> = {
  target_pe: "Target P/E",
  target_pb: "Target P/B",
  target_ev_ebitda: "Target EV/EBITDA",
  target_ev_ebit: "Target EV/EBIT",
  target_ev_fcf: "Target EV/FCF",
};
