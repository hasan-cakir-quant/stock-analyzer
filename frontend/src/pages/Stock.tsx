/**
 * Stock page shell (Task 18). Hosts the metadata header plus slot
 * placeholders for the panels delivered in Tasks 19–23.
 */

import { Download, Pencil, RefreshCw } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { CollapsibleSection } from "@/components/CollapsibleSection";
import { ApiError } from "@/lib/api";
import { type FetchAllResult, useFetchAll } from "@/lib/fetchAll";
import { useCurrencyFormat } from "@/lib/settings";
import { useLookupCik, useStock } from "@/lib/stocks";
import { useAnalysisResult } from "@/stores/analysis";
import { useToast } from "@/stores/toast";
import { EditMetadataDialog } from "@/features/stocks/EditMetadataDialog";
import { GraphsSection } from "@/features/stock-page/graphs/GraphsSection";
import { FinancialsGrid } from "@/features/stock-page/financials/FinancialsGrid";
import { ParameterPanel } from "@/features/stock-page/parameters/ParameterPanel";
import { GradesSection } from "@/features/stock-page/results/GradesSection";
import { GrowthBarCards } from "@/features/stock-page/results/GrowthBarCards";
import { MaValuationPanel } from "@/features/stock-page/results/MaValuationPanel";
import { SnapshotLog } from "@/features/stock-page/snapshots/SnapshotLog";

export default function Stock() {
  const { symbol = "" } = useParams<{ symbol: string }>();
  const stockQuery = useStock(symbol);
  const lookupCik = useLookupCik(symbol);
  const fetchAll = useFetchAll(symbol);
  const toast = useToast();
  const formatCurrency = useCurrencyFormat();
  const analysisResult = useAnalysisResult(symbol);
  const [metadataOpen, setMetadataOpen] = useState(false);

  async function handleLookupCik() {
    try {
      const updated = await lookupCik.mutateAsync();
      toast.show(`CIK ${updated.cik}`, { tone: "success" });
    } catch (err) {
      toast.show(
        err instanceof Error ? `CIK lookup failed — ${err.message}` : "CIK lookup failed.",
        { tone: "error" },
      );
    }
  }

  async function handleFetchAll() {
    try {
      const result = await fetchAll.mutateAsync();
      const { message, anyFailed } = summarizeFetchAll(result);
      toast.show(message, { tone: anyFailed ? "error" : "success" });
    } catch (err) {
      toast.show(
        err instanceof Error ? `Fetch failed — ${err.message}` : "Fetch failed.",
        { tone: "error" },
      );
    }
  }

  if (stockQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">Loading {symbol}…</p>;
  }

  if (stockQuery.isError) {
    const isNotFound =
      stockQuery.error instanceof ApiError && stockQuery.error.status === 404;
    return (
      <div className="space-y-3">
        <h1 className="text-2xl font-semibold tracking-tight">{symbol}</h1>
        {isNotFound ? (
          <EmptyState symbol={symbol} />
        ) : (
          <p className="text-sm text-destructive">
            Couldn’t load this stock. {(stockQuery.error as Error).message}
          </p>
        )}
      </div>
    );
  }

  const stock = stockQuery.data!;

  return (
    <div className="space-y-1.5">
      <header className="flex flex-wrap items-end justify-between gap-2 border-b border-border pb-1">
        <div className="flex items-baseline gap-2">
          <h1 className="text-lg font-semibold tracking-tight">{stock.symbol}</h1>
          <span className="rounded-md border border-border bg-secondary px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
            {stock.currency}
          </span>
          {stock.shares_outstanding !== null && (
            <span className="text-[11px] text-muted-foreground">
              {formatCurrency(stock.shares_outstanding)} shares
            </span>
          )}
          {stock.cik && (
            <a
              href={`https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${stock.cik}`}
              target="_blank"
              rel="noreferrer noopener"
              title="Open this issuer on SEC EDGAR"
              className="text-[11px] font-mono text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
            >
              CIK {stock.cik}
            </a>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={handleFetchAll}
            disabled={fetchAll.isPending}
            title="Fetch financials, closing prices, CIK & market data from SEC EDGAR and Yahoo Finance"
            className="inline-flex items-center gap-1 rounded-md bg-primary px-2 py-0.5 text-[11px] font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
          >
            <RefreshCw className={`h-3 w-3 ${fetchAll.isPending ? "animate-spin" : ""}`} />
            {fetchAll.isPending ? "Fetching…" : "Fetch all data"}
          </button>
          <button
            type="button"
            onClick={handleLookupCik}
            disabled={lookupCik.isPending}
            title="Resolve this stock's CIK from SEC EDGAR"
            className="inline-flex items-center gap-1 rounded-md border border-border bg-secondary px-2 py-0.5 text-[11px] text-secondary-foreground hover:bg-accent disabled:opacity-50"
          >
            <Download className="h-3 w-3" />
            {lookupCik.isPending ? "Fetching…" : stock.cik ? "Refresh CIK" : "Fetch CIK"}
          </button>
          <button
            type="button"
            onClick={() => setMetadataOpen(true)}
            className="inline-flex items-center gap-1 rounded-md border border-border bg-secondary px-2 py-0.5 text-[11px] text-secondary-foreground hover:bg-accent"
          >
            <Pencil className="h-3 w-3" />
            Edit metadata
          </button>
        </div>
      </header>

      <ParameterPanel symbol={stock.symbol} />

      <MaValuationPanel
        symbol={stock.symbol}
        currency={stock.currency}
        isFinancial={stock.is_financial}
      />

      <GradesSection symbol={stock.symbol} />

      {analysisResult ? (
        <GrowthBarCards symbol={stock.symbol} growth={analysisResult.growth} />
      ) : (
        <CollapsibleSection title="Growth">
          <p className="text-xs text-muted-foreground">
            Calculating growth metrics…
          </p>
        </CollapsibleSection>
      )}

      <GraphsSection symbol={stock.symbol} isFinancial={stock.is_financial} />

      <FinancialsGrid
        symbol={stock.symbol}
        stockSharesOutstanding={stock.shares_outstanding}
        unitsNote={stock.units_note}
      />
      <SnapshotLog symbol={stock.symbol} currency={stock.currency} />

      <EditMetadataDialog
        open={metadataOpen}
        onClose={() => setMetadataOpen(false)}
        stock={stock}
      />
    </div>
  );
}

function summarizeFetchAll(result: FetchAllResult): { message: string; anyFailed: boolean } {
  const s = result.steps;
  const parts: string[] = [];
  let anyFailed = false;

  if (s.cik) {
    if (s.cik.ok) parts.push(`CIK ${s.cik.value ?? "✓"}`);
    else {
      parts.push("CIK ✗");
      anyFailed = true;
    }
  }
  if (s.financials) {
    if (s.financials.ok) parts.push(`financials ${s.financials.written ?? 0}q`);
    else {
      parts.push("financials ✗");
      anyFailed = true;
    }
  }
  if (s.closing_prices) {
    if (s.closing_prices.ok) parts.push(`prices ${s.closing_prices.written ?? 0}`);
    else {
      parts.push("prices ✗");
      anyFailed = true;
    }
  }
  if (s.market_data) {
    if (s.market_data.ok) parts.push("price & beta ✓");
    else {
      parts.push("price & beta ✗");
      anyFailed = true;
    }
  }

  return {
    message: `${result.source.toUpperCase()}: ${parts.join(" · ")}`,
    anyFailed,
  };
}

function EmptyState({ symbol }: { symbol: string }) {
  return (
    <div className="rounded-md border border-border bg-card p-4 text-sm">
      <p className="text-muted-foreground">
        No stock with symbol{" "}
        <span className="font-mono text-foreground">{symbol}</span> yet.
      </p>
      <Link
        to="/"
        className="mt-2 inline-block text-primary underline-offset-2 hover:underline"
      >
        ← Back to portfolio
      </Link>
    </div>
  );
}
