/**
 * Dev preview — Storybook-style page rendering every shared primitive
 * with sample props. Satisfies the DoD for Task 16.
 *
 * Reachable at /dev. Not linked from the sidebar — this is a developer
 * surface, not a user-facing page.
 */

import { useState } from "react";

import { CollapsibleSection } from "@/components/CollapsibleSection";
import { DebouncedInput } from "@/components/DebouncedInput";
import { FairValueCard } from "@/components/FairValueCard";
import { GradeChip } from "@/components/GradeChip";
import { MetricRow } from "@/components/MetricRow";
import { SaveIndicator } from "@/components/SaveIndicator";

export default function Dev() {
  const [demoValue, setDemoValue] = useState("Apple Inc.");

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Component preview</h1>
        <p className="text-sm text-muted-foreground">
          Sample renderings for the shared primitives built in Task 16.
        </p>
      </header>

      <Group title="SaveIndicator">
        <div className="flex items-center gap-4 text-sm">
          <Label text="idle" />
          <SaveIndicator state="idle" />
          <Label text="saving" />
          <SaveIndicator state="saving" />
          <Label text="saved" />
          <SaveIndicator state="saved" />
          <Label text="error" />
          <SaveIndicator state="error" />
        </div>
      </Group>

      <Group title="DebouncedInput">
        <div className="grid max-w-md gap-3">
          <DebouncedInput
            label="Symbol notes (auto-saves after 500ms; logs to console)"
            value={demoValue}
            onSave={async (next) => {
              await new Promise((r) => setTimeout(r, 400));
              setDemoValue(next);
              // eslint-disable-next-line no-console
              console.log("[DebouncedInput] saved:", next);
            }}
          />
          <DebouncedInput
            label="Always-error variant (rejects on save)"
            value=""
            onSave={async () => {
              await new Promise((_, reject) => setTimeout(() => reject(new Error("nope")), 400));
            }}
          />
        </div>
      </Group>

      <Group title="GradeChip">
        <div className="flex flex-wrap items-center gap-2">
          <GradeChip value={92} label="General" />
          <GradeChip value={72} label="Profitability" />
          <GradeChip value={55} label="Valuation" />
          <GradeChip value={28} label="Growth" />
          <GradeChip value={null} label="Dividend" />
          <GradeChip value={88} size="lg" />
          <GradeChip value={64} size="sm" />
        </div>
      </Group>

      <Group title="FairValueCard">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <FairValueCard
            model="dcf"
            fairValue={200}
            currentPrice={180}
            computable
            currency="USD"
          />
          <FairValueCard
            model="graham_number"
            fairValue={150}
            currentPrice={180}
            computable
            currency="USD"
          />
          <FairValueCard
            model="ddm"
            fairValue={null}
            currentPrice={180}
            computable={false}
            reason="No dividend history."
            currency="USD"
          />
        </div>
      </Group>

      <Group title="MetricRow">
        <div className="grid max-w-md gap-1">
          <MetricRow label="Revenue (TTM)" value={1234567.89} format="currency" currency="USD" />
          <MetricRow label="Gross margin" value={0.42} format="percent" fromFraction />
          <MetricRow label="Forecast horizon" value={5} format="number" unit="yrs" />
          <MetricRow label="P/E ratio" value={null} format="number" />
        </div>
      </Group>

      <Group title="CollapsibleSection">
        <CollapsibleSection
          title="Income statement"
          trailing={<SaveIndicator state="saved" />}
        >
          <div className="text-sm text-muted-foreground">
            Body content — could be the data-entry grid, a chart, etc.
          </div>
        </CollapsibleSection>
        <CollapsibleSection title="Closed by default" defaultOpen={false}>
          <div className="text-sm text-muted-foreground">Hidden until you click the header.</div>
        </CollapsibleSection>
      </Group>
    </div>
  );
}

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </h2>
      <div className="space-y-2 rounded-md border border-border bg-card p-3">{children}</div>
    </section>
  );
}

function Label({ text }: { text: string }) {
  return <span className="text-xs uppercase tracking-wide text-muted-foreground">{text}</span>;
}
