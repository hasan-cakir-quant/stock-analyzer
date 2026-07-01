/**
 * Settings page (Task 17).
 *
 * Five sections, each auto-saving 500 ms after the user stops typing:
 *   1. General Grade weights        — 7 inputs + sum-to-100 indicator
 *   2. Sub-grade internal weights   — 7 collapsible groups, each summed
 *   3. Grade thresholds             — read-only display + per-metric reset
 *   4. Currency / number formatting — 3 inputs
 *   5. Global Market Assumptions    — N numeric inputs
 *
 * The save model: each `<DebouncedInput />` updates a page-level `draft`
 * and PUTs the entire merged settings payload. Sums are validated client-
 * side; an invalid section throws so the input goes red and the section's
 * sum badge explains why.
 */

import { useEffect, useMemo, useState } from "react";

import { CollapsibleSection } from "@/components/CollapsibleSection";
import { DebouncedInput } from "@/components/DebouncedInput";
import { SumBadge } from "@/features/settings/SumBadge";
import {
  ASSUMPTION_LABELS,
  DEFAULT_GRADE_THRESHOLDS,
  DEFAULT_GLOBAL_MARKET_ASSUMPTIONS,
  METRIC_LABELS,
  SUB_GRADE_LABELS,
  type ThresholdSpec,
} from "@/lib/defaults";
import {
  type Settings as SettingsPayload,
  type SettingsUpdate,
  useSettings,
  useUpdateSettings,
} from "@/lib/settings";
import { useToast } from "@/stores/toast";

const SUB_GRADE_ORDER = [
  "profitability",
  "valuation",
  "financial_strength",
  "growth",
  "efficiency",
  "safety",
  "dividend",
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Coerce a string-or-number to number; returns 0 for invalid so sums work. */
function num(v: unknown): number {
  if (v === null || v === undefined || v === "") return 0;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : 0;
}

function sumValues(record: Record<string, unknown>): number {
  return Object.values(record).reduce<number>((acc, v) => acc + num(v), 0);
}

function shapeForPut(settings: SettingsPayload): SettingsUpdate {
  return {
    general_grade_weights: settings.general_grade_weights,
    sub_grade_weights: settings.sub_grade_weights,
    grade_thresholds: settings.grade_thresholds,
    currency_format: settings.currency_format,
    global_market_assumptions: settings.global_market_assumptions,
  };
}

class ValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ValidationError";
  }
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function Settings() {
  const settingsQuery = useSettings();
  const updateMutation = useUpdateSettings();
  const toast = useToast();

  const [draft, setDraft] = useState<SettingsPayload | null>(null);

  // Pull the server payload into the local draft on first load and whenever
  // the server data changes from outside (rare, but keeps things honest).
  useEffect(() => {
    if (settingsQuery.data && draft === null) {
      setDraft(settingsQuery.data);
    }
  }, [settingsQuery.data, draft]);

  if (settingsQuery.isLoading || !draft) {
    return (
      <p className="text-sm text-muted-foreground">Loading settings…</p>
    );
  }

  if (settingsQuery.isError) {
    return (
      <p className="text-sm text-destructive">
        Couldn’t load settings. Refresh the page.
      </p>
    );
  }

  // Pushes the latest draft to the API. Reads `next` from a callback so
  // each input can pass its own about-to-commit value rather than racing
  // React state updates.
  async function persist(builder: (current: SettingsPayload) => SettingsPayload): Promise<void> {
    const next = builder(draft!);
    setDraft(next);

    // Validate sums client-side so we don't bother the backend with 422s.
    const generalSum = sumValues(next.general_grade_weights);
    if (generalSum !== 100) {
      throw new ValidationError(`General weights must sum to 100 (got ${generalSum}).`);
    }
    for (const group of SUB_GRADE_ORDER) {
      const groupSum = sumValues(next.sub_grade_weights[group] ?? {});
      if (groupSum !== 100) {
        throw new ValidationError(
          `${SUB_GRADE_LABELS[group]} internal weights must sum to 100 (got ${groupSum}).`,
        );
      }
    }

    await updateMutation.mutateAsync(shapeForPut(next));
  }

  return (
    <div className="space-y-2">
      <header>
        <h1 className="text-lg font-semibold tracking-tight">Settings</h1>
        <p className="text-[11px] text-muted-foreground">
          Edits auto-save 500 ms after you stop typing.
        </p>
      </header>

      <GeneralWeightsCard draft={draft} persist={persist} />
      <SubGradeWeightsCard draft={draft} persist={persist} />
      <ThresholdsCard
        draft={draft}
        onResetMetric={(metric) =>
          persist((current) => ({
            ...current,
            grade_thresholds: {
              ...current.grade_thresholds,
              [metric]: DEFAULT_GRADE_THRESHOLDS[metric],
            },
          })).then(() => toast.show(`${METRIC_LABELS[metric] ?? metric} reset to default`, { tone: "success" }))
        }
      />
      <CurrencyFormatCard draft={draft} persist={persist} />
      <GlobalAssumptionsCard draft={draft} persist={persist} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section components
// ---------------------------------------------------------------------------

interface SectionProps {
  draft: SettingsPayload;
  persist: (builder: (current: SettingsPayload) => SettingsPayload) => Promise<void>;
}

function GeneralWeightsCard({ draft, persist }: SectionProps) {
  const sum = sumValues(draft.general_grade_weights);
  return (
    <CollapsibleSection
      title="General Grade weights"
      trailing={<SumBadge sum={sum} />}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        {SUB_GRADE_ORDER.map((key) => (
          <DebouncedInput
            key={key}
            label={SUB_GRADE_LABELS[key]}
            type="number"
            inputMode="numeric"
            value={String(draft.general_grade_weights[key] ?? "")}
            onSave={(next) =>
              persist((current) => ({
                ...current,
                general_grade_weights: {
                  ...current.general_grade_weights,
                  [key]: next === "" ? 0 : Number(next),
                },
              }))
            }
          />
        ))}
      </div>
    </CollapsibleSection>
  );
}

function SubGradeWeightsCard({ draft, persist }: SectionProps) {
  return (
    <CollapsibleSection title="Sub-grade internal weights" defaultOpen={false}>
      <div className="space-y-2">
        {SUB_GRADE_ORDER.map((group) => {
          const weights = draft.sub_grade_weights[group] ?? {};
          const sum = sumValues(weights);
          return (
            <CollapsibleSection
              key={group}
              title={SUB_GRADE_LABELS[group]}
              trailing={<SumBadge sum={sum} />}
              defaultOpen={false}
            >
              <div className="grid gap-3 sm:grid-cols-2">
                {Object.keys(weights).map((metric) => (
                  <DebouncedInput
                    key={metric}
                    label={METRIC_LABELS[metric] ?? metric}
                    type="number"
                    inputMode="numeric"
                    value={String(weights[metric] ?? "")}
                    onSave={(next) =>
                      persist((current) => ({
                        ...current,
                        sub_grade_weights: {
                          ...current.sub_grade_weights,
                          [group]: {
                            ...(current.sub_grade_weights[group] ?? {}),
                            [metric]: next === "" ? 0 : Number(next),
                          },
                        },
                      }))
                    }
                  />
                ))}
              </div>
            </CollapsibleSection>
          );
        })}
      </div>
    </CollapsibleSection>
  );
}

function ThresholdsCard({
  draft,
  onResetMetric,
}: {
  draft: SettingsPayload;
  onResetMetric: (metric: string) => void;
}) {
  const grouped = useMemo(() => groupedMetrics(draft), [draft]);
  return (
    <CollapsibleSection title="Grade thresholds" defaultOpen={false}>
      <p className="mb-3 text-xs text-muted-foreground">
        Per-metric scoring bands. Reset any metric to its sensible default below.
      </p>
      <div className="space-y-2">
        {SUB_GRADE_ORDER.map((group) => {
          const metrics = grouped[group] ?? [];
          if (metrics.length === 0) return null;
          return (
            <CollapsibleSection
              key={group}
              title={SUB_GRADE_LABELS[group]}
              defaultOpen={false}
            >
              <div className="space-y-2">
                {metrics.map((metric) => (
                  <ThresholdRow
                    key={metric}
                    metric={metric}
                    current={draft.grade_thresholds[metric] as ThresholdSpec | undefined}
                    onReset={() => onResetMetric(metric)}
                  />
                ))}
              </div>
            </CollapsibleSection>
          );
        })}
      </div>
    </CollapsibleSection>
  );
}

function groupedMetrics(draft: SettingsPayload): Record<string, string[]> {
  // Walk sub_grade_weights to discover which metrics belong to each group.
  // (`grade_thresholds` is keyed by metric only.)
  const out: Record<string, string[]> = {};
  for (const group of SUB_GRADE_ORDER) {
    out[group] = Object.keys(draft.sub_grade_weights[group] ?? {});
  }
  return out;
}

function ThresholdRow({
  metric,
  current,
  onReset,
}: {
  metric: string;
  current: ThresholdSpec | undefined;
  onReset: () => void;
}) {
  const def = DEFAULT_GRADE_THRESHOLDS[metric];
  const matchesDefault = JSON.stringify(current) === JSON.stringify(def);

  return (
    <div className="rounded-md border border-border bg-background p-2 text-xs">
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium">{METRIC_LABELS[metric] ?? metric}</span>
        <div className="flex items-center gap-2">
          <span
            className={
              matchesDefault
                ? "rounded bg-success/15 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-success"
                : "rounded bg-warning/15 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-warning"
            }
          >
            {matchesDefault ? "default" : "custom"}
          </span>
          <button
            type="button"
            onClick={onReset}
            disabled={matchesDefault}
            className="rounded-md border border-border bg-secondary px-2 py-0.5 text-[11px] disabled:cursor-not-allowed disabled:opacity-50"
          >
            Reset
          </button>
        </div>
      </div>
      <div className="mt-1 text-[11px] text-muted-foreground">
        {current?.direction === "lower_better" ? "Lower is better" : "Higher is better"}{" "}
        ·{" "}
        {(current?.ranges ?? []).map(([boundary, score], i) => (
          <span key={i} className="mr-1.5 tabular-nums">
            {boundary === null ? "else" : `≥ ${boundary}`} → {score}
            {i < (current?.ranges.length ?? 0) - 1 && ","}
          </span>
        ))}
      </div>
    </div>
  );
}

function CurrencyFormatCard({ draft, persist }: SectionProps) {
  const cf = draft.currency_format;
  return (
    <CollapsibleSection title="Currency / number formatting" defaultOpen={false}>
      <div className="grid gap-3 sm:grid-cols-3">
        <DebouncedInput
          label="Thousands separator"
          maxLength={1}
          value={cf.thousands_separator}
          onSave={(next) =>
            persist((current) => ({
              ...current,
              currency_format: { ...current.currency_format, thousands_separator: next },
            }))
          }
        />
        <DebouncedInput
          label="Decimal separator"
          maxLength={1}
          value={cf.decimal_separator}
          onSave={(next) =>
            persist((current) => ({
              ...current,
              currency_format: { ...current.currency_format, decimal_separator: next },
            }))
          }
        />
        <DebouncedInput
          label="Decimal places"
          type="number"
          inputMode="numeric"
          min={0}
          max={8}
          value={String(cf.decimal_places)}
          onSave={(next) =>
            persist((current) => ({
              ...current,
              currency_format: {
                ...current.currency_format,
                decimal_places: next === "" ? 0 : Number(next),
              },
            }))
          }
        />
      </div>
    </CollapsibleSection>
  );
}

function GlobalAssumptionsCard({ draft, persist }: SectionProps) {
  const assumptions = draft.global_market_assumptions ?? {};
  // Keep the iteration order stable / matching the backend defaults.
  const keys = Object.keys(DEFAULT_GLOBAL_MARKET_ASSUMPTIONS);
  return (
    <CollapsibleSection title="Global Market Assumptions">
      <p className="mb-3 text-xs text-muted-foreground">
        Defaults that pre-fill the Target P/E and Target EV/EBITDA inputs in
        each stock's Valuations panel.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        {keys.map((key) => (
          <DebouncedInput
            key={key}
            label={ASSUMPTION_LABELS[key] ?? key}
            type="number"
            step="any"
            inputMode="decimal"
            value={String(assumptions[key] ?? "")}
            onSave={(next) =>
              persist((current) => ({
                ...current,
                global_market_assumptions: {
                  ...current.global_market_assumptions,
                  [key]: next === "" ? null : Number(next),
                },
              }))
            }
          />
        ))}
      </div>
    </CollapsibleSection>
  );
}
