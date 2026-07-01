/**
 * Modal wrapper around `ValuationWorksheet` — used by the comparison
 * table to drill into a single (template × model) cell's calculation
 * breakdown. The table caller passes which template the column belongs
 * to via `columnLabel` so the header makes the context obvious.
 */

import { Modal } from "@/components/Modal";
import { ValuationWorksheet } from "@/components/ValuationWorksheet";
import type { ValuationStep } from "@/lib/analysis";
import { useCurrencyFormat } from "@/lib/settings";

interface WorksheetModalProps {
  open: boolean;
  onClose: () => void;
  /** Template name (or "Current") this column was run with. */
  columnLabel: string;
  /** Pretty model label, e.g. "DCF" or "EV/EBITDA". */
  modelLabel: string;
  /** Internal model name (for the explainer formula/description lookup). */
  modelKey: string;
  steps?: ValuationStep[];
  fairValue: number | null;
  currency?: string | null;
  computable: boolean;
  reason?: string | null;
}

export function WorksheetModal({
  open,
  onClose,
  columnLabel,
  modelLabel,
  modelKey,
  steps,
  fairValue,
  currency,
  computable,
  reason,
}: WorksheetModalProps) {
  const formatCurrency = useCurrencyFormat();

  return (
    <Modal
      open={open}
      onClose={onClose}
      className="max-w-2xl"
      title={
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-semibold">{modelLabel}</span>
          <span className="text-[11px] text-muted-foreground">·</span>
          <span className="text-[11px] text-muted-foreground">{columnLabel}</span>
          {computable && fairValue !== null && (
            <span className="ml-auto text-sm font-semibold tabular-nums">
              {formatCurrency(fairValue, currency)}
            </span>
          )}
        </div>
      }
    >
      <ValuationWorksheet
        model={modelKey}
        steps={steps}
        fairValue={fairValue}
        currency={currency}
        computable={computable}
        reason={reason}
      />
    </Modal>
  );
}
