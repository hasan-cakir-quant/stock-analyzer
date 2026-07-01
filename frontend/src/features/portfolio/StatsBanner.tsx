/**
 * Aggregate stats strip at the top of the Home page.
 * Mirrors FR-3.8.1.2: total stocks, avg general grade, # under/over-valued.
 */

import { ArrowDown, ArrowUp, BarChart3, Layers } from "lucide-react";

import { GradeChip } from "@/components/GradeChip";
import type { PortfolioStats } from "@/lib/portfolio";
import { cn } from "@/lib/utils";

interface StatsBannerProps {
  stats: PortfolioStats;
}

export function StatsBanner({ stats }: StatsBannerProps) {
  const avg =
    stats.average_general_grade === null
      ? null
      : Number(stats.average_general_grade);

  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
      <Tile
        icon={<Layers className="h-3.5 w-3.5" />}
        label="Stocks tracked"
        value={String(stats.total_stocks)}
      />
      <Tile
        icon={<BarChart3 className="h-3.5 w-3.5" />}
        label="Average general grade"
        value={
          avg === null || !Number.isFinite(avg) ? (
            <span className="text-muted-foreground">—</span>
          ) : (
            <GradeChip value={avg} size="md" />
          )
        }
      />
      <Tile
        icon={<ArrowUp className="h-3.5 w-3.5 text-success" />}
        label="Undervalued"
        value={String(stats.undervalued_count)}
        accent="success"
      />
      <Tile
        icon={<ArrowDown className="h-3.5 w-3.5 text-destructive" />}
        label="Overvalued"
        value={String(stats.overvalued_count)}
        accent="destructive"
      />
    </div>
  );
}

interface TileProps {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
  accent?: "success" | "destructive";
}

function Tile({ icon, label, value, accent }: TileProps) {
  return (
    <div
      className={cn(
        "flex items-center justify-between gap-2 rounded-md border border-border bg-card px-2.5 py-1.5",
        accent === "success" && "border-success/30",
        accent === "destructive" && "border-destructive/30",
      )}
    >
      <div className="flex flex-col">
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
          {label}
        </span>
        <span className="text-base font-semibold tabular-nums">{value}</span>
      </div>
      <span className="text-muted-foreground">{icon}</span>
    </div>
  );
}
