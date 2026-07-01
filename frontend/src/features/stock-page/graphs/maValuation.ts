/**
 * Latest-MA valuation helper.
 *
 * For each valuation method, computes the trailing moving average (MA4 / MA8 /
 * MA12) of the stock's *own realized* multiple as of the latest quarter, plus a
 * `fairValue(multiple)` closure that applies any multiple to that quarter's
 * fundamentals. Callers scale the MA by a scenario factor (e.g. pessimist 0.8)
 * before calling `fairValue`. Mirrors the math in HistoricalValuationChart,
 * but only for the latest period.
 */

import type { FinancialRow } from "@/lib/financials";

import { fillIsolatedGaps, movingAverageAt, trailingTtm } from "./ttm";

export const MA_WINDOWS = [4, 8, 12] as const;
export type MaWindow = (typeof MA_WINDOWS)[number];

export interface MaMethod {
  key: string;
  label: string;
  /** EV-based methods don't apply to financials. */
  ev: boolean;
  /** Latest trailing MA of the realized multiple, per window. */
  ma: Record<MaWindow, number | null>;
  /** Apply a (scenario-scaled) multiple to the latest fundamentals → fair px. */
  fairValue: (multiple: number) => number | null;
}

function num(v: string | null): number | null {
  return v === null ? null : Number(v);
}

function maAt(series: (number | null)[], i: number): Record<MaWindow, number | null> {
  return {
    4: movingAverageAt(series, i, 4),
    8: movingAverageAt(series, i, 8),
    12: movingAverageAt(series, i, 12),
  };
}

export function computeMaMethods(rowsInput: FinancialRow[]): MaMethod[] {
  const rows = rowsInput.slice().sort((a, b) => a.period.localeCompare(b.period));
  const last = rows.length - 1;
  if (last < 0) return [];

  const filledEps = fillIsolatedGaps(rows.map((r) => num(r.eps_diluted)));
  const filledRevenue = fillIsolatedGaps(rows.map((r) => num(r.revenue)));
  const filledEbitda = fillIsolatedGaps(rows.map((r) => num(r.ebitda)));
  const filledEbit = fillIsolatedGaps(rows.map((r) => num(r.operating_income)));
  const filledFcf = fillIsolatedGaps(rows.map((r) => num(r.free_cash_flow)));

  const ev: (number | null)[] = rows.map((r) => {
    const price = num(r.closing_price);
    const shares = num(r.shares_outstanding_diluted);
    if (price === null || shares === null) return null;
    const netDebt =
      (num(r.long_term_debt) ?? 0) + (num(r.short_term_debt) ?? 0) - (num(r.cash_and_equivalents) ?? 0);
    return price * shares + netDebt;
  });
  const bvps: (number | null)[] = rows.map((r) => {
    const equity = num(r.total_equity);
    const shares = num(r.shares_outstanding_diluted);
    return equity !== null && shares !== null && shares > 0 ? equity / shares : null;
  });

  const realizedPe = rows.map((r, i) => {
    const price = num(r.closing_price);
    const ttm = trailingTtm(filledEps, i);
    return price !== null && ttm !== null && ttm > 0 ? price / ttm : null;
  });
  const realizedPb = rows.map((r, i) => {
    const price = num(r.closing_price);
    return price !== null && bvps[i] !== null && (bvps[i] as number) > 0
      ? price / (bvps[i] as number)
      : null;
  });
  // Sales per share is TTM revenue / shares (revenue is a flow); P/S = price / SPS.
  const sps: (number | null)[] = rows.map((r, i) => {
    const shares = num(r.shares_outstanding_diluted);
    const ttm = trailingTtm(filledRevenue, i);
    return ttm !== null && shares !== null && shares > 0 ? ttm / shares : null;
  });
  const realizedPs = rows.map((r, i) => {
    const price = num(r.closing_price);
    return price !== null && sps[i] !== null && (sps[i] as number) > 0
      ? price / (sps[i] as number)
      : null;
  });
  const realizedEv = (filled: (number | null)[]) =>
    rows.map((_, i) => {
      const ttm = trailingTtm(filled, i);
      return ev[i] !== null && (ev[i] as number) > 0 && ttm !== null && ttm > 0
        ? (ev[i] as number) / ttm
        : null;
    });
  const realizedEvEbitda = realizedEv(filledEbitda);
  const realizedEvEbit = realizedEv(filledEbit);
  const realizedEvFcf = realizedEv(filledFcf);

  // Latest fundamentals used to turn a multiple into a per-share fair value.
  const sharesLatest = num(rows[last].shares_outstanding_diluted);
  const netDebtLatest =
    (num(rows[last].long_term_debt) ?? 0) +
    (num(rows[last].short_term_debt) ?? 0) -
    (num(rows[last].cash_and_equivalents) ?? 0);
  const ttmEpsLatest = trailingTtm(filledEps, last);
  const ttmEbitdaLatest = trailingTtm(filledEbitda, last);
  const ttmEbitLatest = trailingTtm(filledEbit, last);
  const ttmFcfLatest = trailingTtm(filledFcf, last);
  const bvpsLatest = bvps[last];
  const spsLatest = sps[last];

  const evFair = (ttmLatest: number | null) => (mult: number): number | null =>
    ttmLatest !== null && sharesLatest !== null && sharesLatest > 0
      ? (mult * ttmLatest - netDebtLatest) / sharesLatest
      : null;

  return [
    {
      key: "pe",
      label: "P/E",
      ev: false,
      ma: maAt(realizedPe, last),
      fairValue: (m) => (ttmEpsLatest !== null ? m * ttmEpsLatest : null),
    },
    {
      key: "pb",
      label: "P/B",
      ev: false,
      ma: maAt(realizedPb, last),
      fairValue: (m) => (bvpsLatest !== null ? m * bvpsLatest : null),
    },
    {
      key: "ps",
      label: "P/S",
      ev: false,
      ma: maAt(realizedPs, last),
      fairValue: (m) => (spsLatest !== null ? m * spsLatest : null),
    },
    {
      key: "evEbitda",
      label: "EV/EBITDA",
      ev: true,
      ma: maAt(realizedEvEbitda, last),
      fairValue: evFair(ttmEbitdaLatest),
    },
    {
      key: "evEbit",
      label: "EV/EBIT",
      ev: true,
      ma: maAt(realizedEvEbit, last),
      fairValue: evFair(ttmEbitLatest),
    },
    {
      key: "evFcf",
      label: "EV/FCF",
      ev: true,
      ma: maAt(realizedEvFcf, last),
      fairValue: evFair(ttmFcfLatest),
    },
  ];
}
