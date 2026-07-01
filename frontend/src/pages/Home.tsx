/**
 * Home — Portfolio Overview (Task 24).
 *
 * Sits on top of `GET /api/portfolio/overview` (Task 14), which already
 * pre-shapes per-stock rows from each stock's latest live snapshot, so
 * this page is purely presentational: stats banner, grade-distribution
 * histogram, and the sortable/filterable table with sub-grade chips and
 * a per-row sparkline.
 */

import { Plus } from "lucide-react";
import { useState } from "react";

import { GradeDistribution } from "@/features/portfolio/GradeDistribution";
import { PortfolioTable } from "@/features/portfolio/PortfolioTable";
import { StatsBanner } from "@/features/portfolio/StatsBanner";
import { AddStockDialog } from "@/features/stocks/AddStockDialog";
import { usePortfolioOverview } from "@/lib/portfolio";

export default function Home() {
  const overviewQuery = usePortfolioOverview();
  const [addOpen, setAddOpen] = useState(false);

  return (
    <section className="space-y-2">
      <header className="flex items-center justify-between gap-2 border-b border-border pb-1.5">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Portfolio</h1>
          <p className="text-[11px] text-muted-foreground">
            Aggregate stats and the latest snapshot per stock.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setAddOpen(true)}
          className="inline-flex items-center gap-1 rounded-md bg-primary px-2.5 py-1 text-[11px] font-medium text-primary-foreground hover:opacity-90"
        >
          <Plus className="h-3 w-3" />
          Add stock
        </button>
      </header>

      {overviewQuery.isLoading ? (
        <p className="text-xs text-muted-foreground">Loading portfolio…</p>
      ) : overviewQuery.isError ? (
        <p className="text-xs text-destructive">
          Couldn't load the portfolio. {(overviewQuery.error as Error).message}
        </p>
      ) : overviewQuery.data ? (
        <>
          <StatsBanner stats={overviewQuery.data.stats} />
          <GradeDistribution stocks={overviewQuery.data.stocks} />
          <PortfolioTable stocks={overviewQuery.data.stocks} />
        </>
      ) : null}

      <AddStockDialog open={addOpen} onClose={() => setAddOpen(false)} />
    </section>
  );
}
