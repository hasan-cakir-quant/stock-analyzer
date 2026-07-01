/**
 * SnapshotDetailDialog — opens when the user clicks a row in the
 * Snapshot Log. Shows everything frozen into the snapshot: header
 * summary, valuations, grades, growth, parameters used, and the
 * quarters-of-data the analysis ran against.
 *
 * The dialog renders a deferred query — only triggers the GET /snapshots/{id}
 * fetch when `snapshotId` is non-null.
 */

import { GradeChip } from "@/components/GradeChip";
import { Modal } from "@/components/Modal";
import { ASSUMPTION_LABELS, METRIC_LABELS, SUB_GRADE_LABELS } from "@/lib/defaults";
import {
  useAbbreviatedFormat,
  useCurrencyFormat,
  useNumberFormat,
  usePercentFormat,
} from "@/lib/settings";
import { useSnapshotDetail } from "@/lib/snapshots";
import { cn } from "@/lib/utils";

interface SnapshotDetailDialogProps {
  snapshotId: string | null;
  currency: string | null;
  open: boolean;
  onClose: () => void;
}

const VALUATION_MODEL_LABELS: Record<string, string> = {
  pe_based: "P/E Based",
  pb_based: "P/B Based",
  ev_ebitda: "EV/EBITDA",
  ev_ebit: "EV/EBIT",
  ev_fcf: "EV/FCF",
};

const VALUATION_MODEL_ORDER = [
  "pe_based",
  "pb_based",
  "ev_ebitda",
  "ev_ebit",
  "ev_fcf",
] as const;

const SUB_GRADE_ORDER = [
  "profitability",
  "valuation",
  "financial_strength",
  "growth",
  "efficiency",
  "safety",
  "dividend",
] as const;

export function SnapshotDetailDialog({
  snapshotId,
  currency,
  open,
  onClose,
}: SnapshotDetailDialogProps) {
  const detail = useSnapshotDetail(snapshotId);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Snapshot details"
      className="max-w-4xl"
    >
      {detail.isLoading ? (
        <p className="text-xs text-muted-foreground">Loading…</p>
      ) : detail.isError ? (
        <p className="text-xs text-destructive">
          Couldn't load snapshot. {(detail.error as Error).message}
        </p>
      ) : detail.data ? (
        <SnapshotBody snapshot={detail.data} currency={currency} />
      ) : null}
    </Modal>
  );
}

// ---------------------------------------------------------------------------

function SnapshotBody({
  snapshot,
  currency,
}: {
  snapshot: import("@/lib/snapshots").Snapshot;
  currency: string | null;
}) {
  const formatCurrency = useCurrencyFormat();
  const formatAbbreviated = useAbbreviatedFormat();

  const valuations =
    (snapshot.valuations as { models?: Record<string, ValuationModel>; summary?: ValuationSummary }) ?? {};
  const grades =
    (snapshot.grades as { general?: number | null; sub_grades?: Record<string, SubGrade> }) ?? {};
  const growth =
    (snapshot.growth_metrics as { horizons?: string[]; metrics?: Record<string, Record<string, number | null>> }) ?? {};
  const parameters = (snapshot.parameters_used ?? {}) as Record<string, unknown>;
  const financials = snapshot.financials_snapshot ?? [];

  const summary = valuations.summary ?? {};
  const models = valuations.models ?? {};
  const subGrades = grades.sub_grades ?? {};

  return (
    <div className="space-y-3 text-[11px]">
      {/* Header summary */}
      <header className="space-y-1 rounded-md border border-border bg-card/60 px-2 py-1.5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div className="flex items-baseline gap-2">
            <span className="text-xs font-semibold">{snapshot.symbol}</span>
            <span className="font-mono tabular-nums text-muted-foreground">
              {new Date(snapshot.created_at).toLocaleString()}
            </span>
            {snapshot.soft_deleted_at && (
              <span className="rounded bg-muted/40 px-1 py-0.5 text-[9px] uppercase tracking-wide text-muted-foreground">
                soft-deleted {new Date(snapshot.soft_deleted_at).toLocaleDateString()}
              </span>
            )}
          </div>
          <GradeChip value={grades.general ?? null} label="General" size="md" />
        </div>
        <div className="grid gap-1 sm:grid-cols-3">
          <KeyValue
            label={
              snapshot.ma_valuations ? "Value-area fair value" : "Average fair value"
            }
            value={
              summary.average === null || summary.average === undefined
                ? "—"
                : `${formatAbbreviated(Number(summary.average))}${currency ? ` ${currency}` : ""}`
            }
          />
          <KeyValue
            label="Current price used"
            value={
              snapshot.current_price_used === null
                ? "—"
                : formatCurrency(Number(snapshot.current_price_used), currency)
            }
          />
          <KeyValue
            label="Upside / downside"
            value={
              summary.upside_pct === null || summary.upside_pct === undefined
                ? "—"
                : `${Number(summary.upside_pct).toFixed(2)}%`
            }
          />
        </div>
        {snapshot.note && (
          <div className="rounded border border-border bg-background px-1.5 py-1 text-foreground">
            <span className="text-muted-foreground">Note:</span> {snapshot.note}
          </div>
        )}
      </header>

      {/* Valuation — MA-based for new snapshots; legacy default-multiple
          models for older ones saved before the MA valuation existed. */}
      {snapshot.ma_valuations ? (
        <Section title={`MA valuation — ${snapshot.ma_valuations.scenario_label}`}>
          <MaValuationTable ma={snapshot.ma_valuations} currency={currency} />
        </Section>
      ) : (
        <Section title="Valuations (default multiples)">
          <ValuationsTable models={models} currency={currency} />
        </Section>
      )}

      {/* Grades */}
      <Section title="Grades">
        <SubGradeStrip subGrades={subGrades} />
      </Section>

      {/* Growth */}
      {growth.horizons && growth.horizons.length > 0 && (
        <Section title="Growth (CAGRs)">
          <GrowthTable horizons={growth.horizons} metrics={growth.metrics ?? {}} />
        </Section>
      )}

      {/* Parameters used */}
      <Section title="Parameters used">
        <ParametersGrid parameters={parameters} />
      </Section>

      {/* Quarters frozen */}
      <Section title={`Quarters frozen (${financials.length})`}>
        <QuartersList financials={financials} />
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------------------

interface ValuationModel {
  fair_value: number | null;
  computable: boolean;
  reason: string | null;
}

interface ValuationSummary {
  average?: number | null;
  median?: number | null;
  current_price?: number | null;
  upside_pct?: number | null;
}

interface SubGrade {
  score: number | null;
  metrics_used: number;
  metrics_total: number;
  breakdown: Record<string, { value: number | null; score: number | null }>;
}

function MaValuationTable({
  ma,
  currency,
}: {
  ma: import("@/lib/snapshots").MaValuations;
  currency: string | null;
}) {
  const formatCurrency = useCurrencyFormat();
  const windows = ma.methods[0]?.windows.map((w) => w.window) ?? [];
  const cp = ma.current_price;
  const va = ma.value_area;
  return (
    <>
    {va && (
      <p className="mb-1.5 text-[10px] text-muted-foreground">
        Value area (central 70%):{" "}
        <span className="tabular-nums text-foreground">
          {formatCurrency(va.low, currency)} – {formatCurrency(va.high, currency)}
        </span>{" "}
        · mean{" "}
        <span className="font-medium tabular-nums text-foreground">
          {formatCurrency(va.mean, currency)}
        </span>{" "}
        ({va.count} of{" "}
        {ma.methods.reduce(
          (n, m) => n + m.windows.filter((w) => w.fair_value !== null).length,
          0,
        )}{" "}
        estimates)
      </p>
    )}
    <table className="w-full border-collapse text-[11px]">
      <thead>
        <tr className="border-b border-border text-muted-foreground">
          <th className="px-1.5 py-1 text-left font-medium">Method</th>
          {windows.map((w) => (
            <th key={w} className="px-1.5 py-1 text-right font-medium">
              MA{w}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {ma.methods.map((m) => (
          <tr key={m.key} className="border-b border-border/30">
            <td className="px-1.5 py-1 font-medium">{m.label}</td>
            {m.windows.map((w) => {
              const upside =
                w.fair_value !== null && cp !== null && cp > 0
                  ? ((w.fair_value - cp) / cp) * 100
                  : null;
              return (
                <td key={w.window} className="px-1.5 py-1 text-right align-top tabular-nums">
                  {w.fair_value === null ? (
                    <span className="text-muted-foreground">—</span>
                  ) : (
                    <div className="flex flex-col items-end">
                      <span className="font-medium">
                        {formatCurrency(w.fair_value, currency)}
                      </span>
                      {upside !== null && (
                        <span
                          className={
                            upside > 0
                              ? "text-[10px] text-success"
                              : upside < 0
                                ? "text-[10px] text-destructive"
                                : "text-[10px] text-muted-foreground"
                          }
                        >
                          {upside.toFixed(1)}%
                        </span>
                      )}
                    </div>
                  )}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-md border border-border bg-card/40">
      <header className="border-b border-border/60 px-2 py-1 text-[10px] uppercase tracking-wide text-muted-foreground">
        {title}
      </header>
      <div className="px-2 py-1.5">{children}</div>
    </section>
  );
}

function KeyValue({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-2 rounded border border-border bg-background px-1.5 py-0.5">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium tabular-nums">{value}</span>
    </div>
  );
}

function ValuationsTable({
  models,
  currency,
}: {
  models: Record<string, ValuationModel>;
  currency: string | null;
}) {
  const formatCurrency = useCurrencyFormat();
  const presentModels = VALUATION_MODEL_ORDER.filter((name) => models[name] !== undefined);

  if (presentModels.length === 0) {
    return <p className="text-muted-foreground">No valuation models recorded.</p>;
  }

  return (
    <table className="w-full border-separate border-spacing-0">
      <thead>
        <tr className="text-[9px] uppercase tracking-wide text-muted-foreground">
          <th className="px-1 py-0.5 text-left font-medium">Model</th>
          <th className="px-1 py-0.5 text-right font-medium">Fair value</th>
          <th className="px-1 py-0.5 text-left font-medium">Status</th>
        </tr>
      </thead>
      <tbody>
        {presentModels.map((name) => {
          const m = models[name];
          return (
            <tr key={name} className="border-t border-border/60">
              <td className="px-1 py-0.5">
                {VALUATION_MODEL_LABELS[name] ?? name}
              </td>
              <td className="px-1 py-0.5 text-right tabular-nums">
                {m.computable && m.fair_value !== null
                  ? formatCurrency(m.fair_value, currency)
                  : "—"}
              </td>
              <td className="px-1 py-0.5 text-muted-foreground">
                {m.computable ? "Computable" : m.reason ?? "Not computable"}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function SubGradeStrip({ subGrades }: { subGrades: Record<string, SubGrade> }) {
  const presentNames = SUB_GRADE_ORDER.filter((name) => subGrades[name] !== undefined);

  if (presentNames.length === 0) {
    return <p className="text-muted-foreground">No sub-grades recorded.</p>;
  }

  return (
    <div className="space-y-1.5">
      <div className="grid gap-1 sm:grid-cols-3 lg:grid-cols-4">
        {presentNames.map((name) => {
          const sg = subGrades[name];
          return (
            <div
              key={name}
              className="flex items-center justify-between gap-1.5 rounded border border-border bg-background px-1.5 py-0.5"
            >
              <span className="text-muted-foreground">
                {SUB_GRADE_LABELS[name] ?? name}
              </span>
              <div className="flex items-center gap-1">
                <span className="text-[9px] text-muted-foreground">
                  {sg.metrics_used}/{sg.metrics_total}
                </span>
                <GradeChip value={sg.score} size="sm" />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function GrowthTable({
  horizons,
  metrics,
}: {
  horizons: string[];
  metrics: Record<string, Record<string, number | null>>;
}) {
  const formatPercent = usePercentFormat();
  const metricNames = Object.keys(metrics);

  if (metricNames.length === 0) {
    return <p className="text-muted-foreground">No growth metrics recorded.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-separate border-spacing-0">
        <thead>
          <tr className="text-[9px] uppercase tracking-wide text-muted-foreground">
            <th className="px-1 py-0.5 text-left font-medium">Metric</th>
            {horizons.map((h) => (
              <th key={h} className="px-1 py-0.5 text-right font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {metricNames.map((metric) => (
            <tr key={metric} className="border-t border-border/60">
              <td className="px-1 py-0.5">
                {METRIC_LABELS[metric] ?? metric.replace(/_/g, " ")}
              </td>
              {horizons.map((h) => {
                const value = metrics[metric]?.[h] ?? null;
                const positive = value !== null && value > 0;
                const negative = value !== null && value < 0;
                return (
                  <td
                    key={h}
                    className={cn(
                      "px-1 py-0.5 text-right tabular-nums",
                      value === null && "text-muted-foreground/40",
                      positive && "text-success",
                      negative && "text-destructive",
                    )}
                  >
                    {value === null
                      ? "—"
                      : formatPercent(value, { fromFraction: true })}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ParametersGrid({ parameters }: { parameters: Record<string, unknown> }) {
  const formatNumber = useNumberFormat();
  const entries = Object.entries(parameters).filter(
    ([, v]) => v !== null && v !== undefined && v !== "",
  );

  if (entries.length === 0) {
    return <p className="text-muted-foreground">No parameters captured.</p>;
  }

  return (
    <div className="grid gap-1 sm:grid-cols-2 lg:grid-cols-3">
      {entries.map(([key, value]) => {
        const label = ASSUMPTION_LABELS[key] ?? key.replace(/_/g, " ");
        const display =
          typeof value === "number"
            ? formatNumber(value, { decimalPlaces: 4 })
            : String(value);
        return (
          <div
            key={key}
            className="flex items-baseline justify-between gap-1.5 rounded border border-border bg-background px-1.5 py-0.5"
          >
            <span className="text-muted-foreground">{label}</span>
            <span className="font-medium tabular-nums">{display}</span>
          </div>
        );
      })}
    </div>
  );
}

function QuartersList({
  financials,
}: {
  financials: Array<Record<string, unknown>>;
}) {
  if (financials.length === 0) {
    return <p className="text-muted-foreground">No financials captured.</p>;
  }

  // Sort ascending by period so the oldest is first — matches the rest of the app.
  const sorted = [...financials].sort((a, b) => {
    const pa = String(a.period ?? "");
    const pb = String(b.period ?? "");
    return pa.localeCompare(pb);
  });

  return (
    <div className="flex flex-wrap gap-1">
      {sorted.map((row, i) => (
        <span
          key={(row.period as string) ?? i}
          className="rounded border border-border bg-background px-1.5 py-0.5 font-mono text-[10px] tabular-nums"
          title={row.period_end_date ? `Period end: ${row.period_end_date}` : undefined}
        >
          {String(row.period ?? "—")}
        </span>
      ))}
    </div>
  );
}
