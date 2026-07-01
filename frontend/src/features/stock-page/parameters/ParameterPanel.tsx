/**
 * Parameter Panel — pared down to market-data only.
 *
 * Per-stock parameters own just `current_price` and `beta`. The valuation
 * target multiples (Target P/E, Target EV/EBITDA) are entered at run time in
 * the Valuations panel, where the "Run valuation" and "Save snapshot" actions
 * also live.
 */

import { Download } from "lucide-react";
import { useState } from "react";

import { CollapsibleSection } from "@/components/CollapsibleSection";
import { DebouncedInput } from "@/components/DebouncedInput";
import {
  type ParameterField,
  type ParameterUpdate,
  useFetchMarketData,
  useParameters,
  useUpdateParameters,
} from "@/lib/parameters";
import { useToast } from "@/stores/toast";

interface FieldDef {
  key: ParameterField;
  label: string;
  hint?: string;
  step?: string;
}

const FIELDS: FieldDef[] = [
  {
    key: "current_price",
    label: "Current price",
    hint: "per share, in stock currency",
    step: "any",
  },
  { key: "beta", label: "Beta", step: "any" },
];

interface ParameterPanelProps {
  symbol: string;
}

export function ParameterPanel({ symbol }: ParameterPanelProps) {
  const parametersQuery = useParameters(symbol);
  const updateParameters = useUpdateParameters(symbol);
  const fetchMarketData = useFetchMarketData(symbol);
  const toast = useToast();

  const [draft, setDraft] = useState<Partial<Record<ParameterField, string>>>({});

  const saved = parametersQuery.data;

  function readFieldString(field: FieldDef): string {
    const drafted = draft[field.key];
    if (drafted !== undefined) return drafted;
    const value = saved?.[field.key];
    if (value === null || value === undefined) return "";
    return String(value);
  }

  function clearDraftField(field: ParameterField) {
    setDraft((prev) => {
      if (!(field in prev)) return prev;
      const { [field]: _omit, ...rest } = prev;
      return rest;
    });
  }

  async function handleSave(field: FieldDef, value: string) {
    const trimmed = value.trim();
    const payload: ParameterUpdate =
      trimmed === ""
        ? ({ [field.key]: null } as ParameterUpdate)
        : ({ [field.key]: trimmed } as ParameterUpdate);
    await updateParameters.mutateAsync(payload);
    clearDraftField(field.key);
  }

  async function handleFetchMarket() {
    try {
      const data = await fetchMarketData.mutateAsync();
      const patch: ParameterUpdate = {};
      if (data.current_price !== null) patch.current_price = data.current_price;
      if (data.beta !== null) patch.beta = data.beta;
      if (Object.keys(patch).length === 0) {
        toast.show("No market data returned.", { tone: "error" });
        return;
      }
      await updateParameters.mutateAsync(patch);
      setDraft((prev) => {
        const next = { ...prev };
        if ("current_price" in patch) delete next.current_price;
        if ("beta" in patch) delete next.beta;
        return next;
      });
      const parts: string[] = [];
      if (patch.current_price !== undefined) parts.push(`price ${patch.current_price}`);
      if (patch.beta !== undefined) parts.push(`beta ${patch.beta}`);
      toast.show(`Fetched ${parts.join(", ")}`, { tone: "success" });
    } catch (err) {
      toast.show(
        err instanceof Error ? `Fetch failed — ${err.message}` : "Fetch failed.",
        { tone: "error" },
      );
    }
  }

  if (parametersQuery.isLoading) {
    return (
      <CollapsibleSection title="Market Data">
        <p className="text-xs text-muted-foreground">Loading…</p>
      </CollapsibleSection>
    );
  }

  if (parametersQuery.isError) {
    return (
      <CollapsibleSection title="Market Data">
        <p className="text-xs text-destructive">
          Couldn't load market data. {(parametersQuery.error as Error).message}
        </p>
      </CollapsibleSection>
    );
  }

  return (
    <CollapsibleSection title="Market Data">
      <div className="space-y-1.5">
        <div className="grid gap-x-2 gap-y-1 sm:grid-cols-3 md:grid-cols-4">
          {FIELDS.map((field) => (
            <DebouncedInput
              key={field.key}
              label={field.label}
              value={readFieldString(field)}
              type="number"
              inputMode="decimal"
              step={field.step}
              className="h-6 text-[11px]"
              onValueChange={(next) =>
                setDraft((prev) => ({ ...prev, [field.key]: next }))
              }
              onSave={(next) => handleSave(field, next)}
            />
          ))}
        </div>

        <p className="text-[10px] text-muted-foreground">
          Set <span className="font-medium">Target P/E</span> and{" "}
          <span className="font-medium">Target EV/EBITDA</span> in the Valuations
          section below, then run an analysis.
        </p>

        <div className="flex flex-wrap items-center gap-1.5 border-t border-border pt-1.5">
          <button
            type="button"
            onClick={handleFetchMarket}
            disabled={fetchMarketData.isPending}
            title="Fetch current price and beta from Yahoo Finance"
            className="inline-flex items-center gap-1 rounded-md border border-border bg-secondary px-2.5 py-1 text-[11px] text-secondary-foreground hover:bg-accent disabled:opacity-50"
          >
            <Download className="h-3 w-3" />
            {fetchMarketData.isPending ? "Fetching…" : "Fetch price & beta"}
          </button>
          {saved?.updated_at && (
            <span className="ml-auto text-[10px] text-muted-foreground">
              Last saved {new Date(saved.updated_at).toLocaleString()}
            </span>
          )}
        </div>
      </div>
    </CollapsibleSection>
  );
}
