/**
 * Sortable, filterable portfolio table (FR-3.8.1.1).
 *
 * Columns: Symbol · Currency · Category · Notes · Current Price · Avg Fair
 *          Value · Upside · General Grade · Sub-grades · Trend · Last Updated · ⋯
 *
 * Sorting is client-side (data is already a single small list); filtering is a
 * symbol/notes/category substring search plus a category dropdown. Category is
 * editable inline and rows can be deleted from the trailing actions column.
 */

import { ArrowDown, ArrowUp, ArrowUpDown, Search, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { GradeChip } from "@/components/GradeChip";
import { SUB_GRADE_LABELS } from "@/lib/defaults";
import {
  type PortfolioStockRow,
  useDeleteTicker,
  useSetCategory,
} from "@/lib/portfolio";
import {
  useAbbreviatedFormat,
  useCurrencyFormat,
  usePercentFormat,
} from "@/lib/settings";
import { useToast } from "@/stores/toast";
import { cn } from "@/lib/utils";

import { GradeSparkline } from "./GradeSparkline";

interface PortfolioTableProps {
  stocks: PortfolioStockRow[];
}

// Scenario columns (keys match the backend fair-values job).
const SCENARIOS: { key: string; label: string }[] = [
  { key: "super_pessimist", label: "S.Pess" },
  { key: "pessimist", label: "Pess" },
  { key: "normal", label: "Normal" },
  { key: "optimist", label: "Optim" },
  { key: "super_optimist", label: "S.Optim" },
];

type SortColumn =
  | "symbol"
  | "currency"
  | "category"
  | "current_price"
  | "average_fair_value"
  | "upside_pct"
  | "general_grade"
  | "last_updated";

type SortDirection = "asc" | "desc";

interface SortState {
  column: SortColumn;
  direction: SortDirection;
}

const CATEGORY_DATALIST_ID = "portfolio-categories";

const SUB_GRADE_ORDER = [
  "profitability",
  "valuation",
  "financial_strength",
  "growth",
  "efficiency",
  "safety",
  "dividend",
] as const;

const SUB_GRADE_SHORT_LABEL: Record<string, string> = {
  profitability: "Pr",
  valuation: "Va",
  financial_strength: "FS",
  growth: "Gr",
  efficiency: "Ef",
  safety: "Sa",
  dividend: "Di",
};

export function PortfolioTable({ stocks }: PortfolioTableProps) {
  const [filter, setFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [sort, setSort] = useState<SortState>({
    column: "symbol",
    direction: "asc",
  });

  const setCategory = useSetCategory();
  const deleteTicker = useDeleteTicker();
  const toast = useToast();

  const categories = useMemo(() => {
    const set = new Set<string>();
    for (const s of stocks) {
      if (s.category && s.category.trim() !== "") set.add(s.category);
    }
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [stocks]);

  const visible = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    const filtered = stocks.filter((s) => {
      if (categoryFilter && (s.category ?? "") !== categoryFilter) return false;
      if (!needle) return true;
      const haystack = `${s.symbol} ${s.notes ?? ""} ${s.category ?? ""}`.toLowerCase();
      return haystack.includes(needle);
    });
    return [...filtered].sort((a, b) => compareRows(a, b, sort));
  }, [stocks, filter, categoryFilter, sort]);

  function toggleSort(column: SortColumn) {
    setSort((prev) =>
      prev.column === column
        ? { column, direction: prev.direction === "asc" ? "desc" : "asc" }
        : { column, direction: defaultDirection(column) },
    );
  }

  async function handleSetCategory(symbol: string, value: string) {
    const trimmed = value.trim();
    try {
      await setCategory.mutateAsync({ symbol, category: trimmed === "" ? null : trimmed });
    } catch (err) {
      toast.show(
        err instanceof Error ? `Couldn't set category — ${err.message}` : "Couldn't set category.",
        { tone: "error" },
      );
    }
  }

  async function handleDelete(symbol: string) {
    if (!window.confirm(`Delete ${symbol}? This permanently removes its financials, snapshots, and parameters.`)) {
      return;
    }
    try {
      await deleteTicker.mutateAsync(symbol);
      toast.show(`Deleted ${symbol}.`, { tone: "success" });
    } catch (err) {
      toast.show(
        err instanceof Error ? `Delete failed — ${err.message}` : "Delete failed.",
        { tone: "error" },
      );
    }
  }

  return (
    <section className="space-y-2">
      <datalist id={CATEGORY_DATALIST_ID}>
        {categories.map((c) => (
          <option key={c} value={c} />
        ))}
      </datalist>

      <div className="flex flex-wrap items-center gap-1.5">
        <div className="relative flex-1 max-w-xs">
          <Search className="pointer-events-none absolute left-1.5 top-1/2 h-3 w-3 -translate-y-1/2 text-muted-foreground" />
          <input
            type="search"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter symbol, notes, category…"
            className="h-7 w-full rounded-md border border-input bg-background pl-6 pr-2 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="h-7 rounded-md border border-input bg-background px-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
          title="Filter by category"
        >
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <span className="text-[10px] text-muted-foreground">
          {visible.length} of {stocks.length}
        </span>
      </div>

      {visible.length === 0 ? (
        <p className="rounded-md border border-dashed border-border bg-card/40 p-3 text-[11px] text-muted-foreground">
          {stocks.length === 0
            ? "No stocks yet — click Add stock to track your first one."
            : "No matches for that filter."}
        </p>
      ) : (
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full border-separate border-spacing-0 text-[11px]">
            <thead className="bg-card">
              <tr>
                <SortableTh column="symbol" label="Symbol" sort={sort} onClick={toggleSort} />
                <SortableTh column="currency" label="Cur" sort={sort} onClick={toggleSort} />
                <SortableTh column="category" label="Category" sort={sort} onClick={toggleSort} />
                <th className="border-b border-border px-2 py-1 text-left font-medium text-muted-foreground">
                  Notes
                </th>
                <SortableTh column="current_price" label="Price" align="right" sort={sort} onClick={toggleSort} />
                {SCENARIOS.map((s) => (
                  <th
                    key={s.key}
                    className="border-b border-border px-2 py-1 text-right font-medium text-muted-foreground"
                    title={`Fair value · upside — ${s.label} scenario`}
                  >
                    {s.label}
                  </th>
                ))}
                <SortableTh column="general_grade" label="Grade" align="right" sort={sort} onClick={toggleSort} />
                <th className="border-b border-border px-2 py-1 text-left font-medium text-muted-foreground">
                  Sub-grades
                </th>
                <th className="border-b border-border px-2 py-1 text-left font-medium text-muted-foreground">
                  Trend
                </th>
                <SortableTh column="last_updated" label="Last update" align="right" sort={sort} onClick={toggleSort} />
                <th className="border-b border-border px-2 py-1 text-right font-medium text-muted-foreground"></th>
              </tr>
            </thead>
            <tbody>
              {visible.map((row) => (
                <Row
                  key={row.symbol}
                  row={row}
                  onSetCategory={handleSetCategory}
                  onDelete={handleDelete}
                  deleting={deleteTicker.isPending}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------

interface SortableThProps {
  column: SortColumn;
  label: string;
  align?: "left" | "right";
  sort: SortState;
  onClick: (col: SortColumn) => void;
}

function SortableTh({ column, label, align = "left", sort, onClick }: SortableThProps) {
  const active = sort.column === column;
  const Icon = !active ? ArrowUpDown : sort.direction === "asc" ? ArrowUp : ArrowDown;
  return (
    <th
      className={cn(
        "border-b border-border bg-card px-2 py-1 font-medium text-muted-foreground",
        align === "right" ? "text-right" : "text-left",
      )}
    >
      <button
        type="button"
        onClick={() => onClick(column)}
        className={cn(
          "inline-flex items-center gap-0.5 hover:text-foreground focus:outline-none focus:text-foreground",
          align === "right" && "flex-row-reverse",
          active && "text-foreground",
        )}
      >
        {label}
        <Icon className="h-3 w-3 opacity-70" />
      </button>
    </th>
  );
}

function Row({
  row,
  onSetCategory,
  onDelete,
  deleting,
}: {
  row: PortfolioStockRow;
  onSetCategory: (symbol: string, value: string) => void;
  onDelete: (symbol: string) => void;
  deleting: boolean;
}) {
  const formatCurrency = useCurrencyFormat();
  const formatAbbreviated = useAbbreviatedFormat();
  const formatPercent = usePercentFormat();

  return (
    <tr className="border-t border-border/60 hover:bg-accent/40">
      <td className="px-2 py-1 align-middle">
        <Link
          to={`/stocks/${encodeURIComponent(row.symbol)}`}
          className="font-mono font-medium text-foreground hover:text-primary"
        >
          {row.symbol}
        </Link>
      </td>
      <td className="px-2 py-1 align-middle text-muted-foreground">{row.currency}</td>
      <td className="px-2 py-1 align-middle">
        <CategoryCell row={row} onSave={onSetCategory} />
      </td>
      <td
        className="max-w-[200px] truncate px-2 py-1 align-middle text-muted-foreground"
        title={row.notes ?? undefined}
      >
        {row.notes ? row.notes.replace(/[\r\n]+/g, " ") : <span className="italic">—</span>}
      </td>
      <td className="px-2 py-1 text-right align-middle tabular-nums">
        {row.current_price === null
          ? "—"
          : formatCurrency(Number(row.current_price), row.currency)}
      </td>
      {SCENARIOS.map((s) => {
        const cell = row.fair_values?.[s.key];
        const fv = cell?.fair_value ?? null;
        const up = cell?.upside_pct ?? null;
        return (
          <td key={s.key} className="px-2 py-1 text-right align-middle tabular-nums">
            {fv === null ? (
              <span className="text-muted-foreground">—</span>
            ) : (
              <div className="flex flex-col items-end leading-tight">
                <span>{formatAbbreviated(fv)}</span>
                {up !== null && (
                  <span
                    className={cn(
                      "text-[9px]",
                      up > 0 && "text-success",
                      up < 0 && "text-destructive",
                    )}
                  >
                    {formatPercent(up)}
                  </span>
                )}
              </div>
            )}
          </td>
        );
      })}
      <td className="px-2 py-1 text-right align-middle">
        <GradeChip
          value={row.general_grade === null ? null : Number(row.general_grade)}
          size="sm"
        />
      </td>
      <td className="px-2 py-1 align-middle">
        <div className="flex flex-wrap gap-0.5">
          {SUB_GRADE_ORDER.map((name) => {
            const raw = row.sub_grades?.[name];
            const value = raw === null || raw === undefined ? null : Number(raw);
            const short = SUB_GRADE_SHORT_LABEL[name] ?? name.slice(0, 2);
            return (
              <GradeChip
                key={name}
                value={value}
                size="sm"
                label={short}
                incompleteText={`${short} —`}
                title={`${SUB_GRADE_LABELS[name] ?? name}: ${
                  value === null || !Number.isFinite(value)
                    ? "Incomplete"
                    : Math.round(value)
                }`}
                className="px-1"
              />
            );
          })}
        </div>
      </td>
      <td className="px-2 py-1 align-middle">
        <GradeSparkline points={row.sparkline} />
      </td>
      <td className="px-2 py-1 text-right align-middle tabular-nums text-muted-foreground">
        {row.last_updated === null ? "—" : formatRelativeDate(row.last_updated)}
      </td>
      <td className="px-2 py-1 text-right align-middle">
        <button
          type="button"
          onClick={() => onDelete(row.symbol)}
          disabled={deleting}
          aria-label={`Delete ${row.symbol}`}
          title="Delete ticker"
          className="rounded p-0.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive disabled:opacity-50"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </td>
    </tr>
  );
}

function CategoryCell({
  row,
  onSave,
}: {
  row: PortfolioStockRow;
  onSave: (symbol: string, value: string) => void;
}) {
  const [value, setValue] = useState(row.category ?? "");

  // Keep local state in sync if the row's category changes from elsewhere.
  const saved = row.category ?? "";

  function commit() {
    if (value.trim() === saved.trim()) return;
    onSave(row.symbol, value);
  }

  return (
    <input
      list={CATEGORY_DATALIST_ID}
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        if (e.key === "Escape") setValue(saved);
      }}
      placeholder="—"
      className="h-6 w-24 rounded-md border border-transparent bg-transparent px-1 text-[11px] hover:border-input focus:border-input focus:bg-background focus:outline-none focus:ring-1 focus:ring-ring"
    />
  );
}

// ---------------------------------------------------------------------------

function compareRows(
  a: PortfolioStockRow,
  b: PortfolioStockRow,
  sort: SortState,
): number {
  const direction = sort.direction === "asc" ? 1 : -1;
  switch (sort.column) {
    case "symbol":
      return a.symbol.localeCompare(b.symbol) * direction;
    case "currency":
      return a.currency.localeCompare(b.currency) * direction;
    case "category":
      return textCompare(a.category, b.category) * direction;
    case "current_price":
      return numericCompare(a.current_price, b.current_price) * direction;
    case "average_fair_value":
      return numericCompare(a.average_fair_value, b.average_fair_value) * direction;
    case "upside_pct":
      return numericCompare(a.upside_pct, b.upside_pct) * direction;
    case "general_grade":
      return numericCompare(a.general_grade, b.general_grade) * direction;
    case "last_updated":
      return dateCompare(a.last_updated, b.last_updated) * direction;
  }
}

function textCompare(a: string | null, b: string | null): number {
  // Empty / null categories sort to the bottom regardless of direction.
  const av = a && a.trim() !== "" ? a : null;
  const bv = b && b.trim() !== "" ? b : null;
  if (av === null && bv === null) return 0;
  if (av === null) return 1;
  if (bv === null) return -1;
  return av.localeCompare(bv);
}

function numericCompare(a: string | null, b: string | null): number {
  // Push nulls to the bottom regardless of direction so an "asc by grade"
  // doesn't bury the highest-grade rows below dead "no snapshot" rows.
  const av = a === null ? null : Number(a);
  const bv = b === null ? null : Number(b);
  if (av === null && bv === null) return 0;
  if (av === null) return 1;
  if (bv === null) return -1;
  if (!Number.isFinite(av) && !Number.isFinite(bv)) return 0;
  if (!Number.isFinite(av)) return 1;
  if (!Number.isFinite(bv)) return -1;
  return av - bv;
}

function dateCompare(a: string | null, b: string | null): number {
  if (a === null && b === null) return 0;
  if (a === null) return 1;
  if (b === null) return -1;
  return new Date(a).getTime() - new Date(b).getTime();
}

function defaultDirection(column: SortColumn): SortDirection {
  // Numeric / date columns default to descending so the best/most-recent
  // rows surface first; text columns default to ascending.
  if (column === "symbol" || column === "currency" || column === "category") return "asc";
  return "desc";
}

function formatRelativeDate(iso: string): string {
  const then = new Date(iso).getTime();
  const now = Date.now();
  const diffMs = now - then;
  const day = 24 * 60 * 60 * 1000;
  if (diffMs < 60 * 60 * 1000) return "just now";
  if (diffMs < day) return `${Math.floor(diffMs / (60 * 60 * 1000))}h ago`;
  if (diffMs < 7 * day) return `${Math.floor(diffMs / day)}d ago`;
  return new Date(iso).toLocaleDateString(undefined, {
    year: "2-digit",
    month: "short",
    day: "2-digit",
  });
}
