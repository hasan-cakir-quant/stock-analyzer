/**
 * Edit Metadata dialog — symbol is read-only after creation (FR-3.1.4).
 * Currency, shares outstanding, and notes auto-save 500 ms after editing.
 * Notes get an opt-in markdown preview using the tiny renderer in
 * src/lib/markdown.ts (which escapes HTML and only emits a small subset).
 */

import { useState } from "react";

import { DebouncedInput } from "@/components/DebouncedInput";
import { DebouncedTextarea } from "@/components/DebouncedTextarea";
import { Modal } from "@/components/Modal";
import { renderMarkdownToHtml } from "@/lib/markdown";
import { type Stock, useUpdateStock } from "@/lib/stocks";

interface EditMetadataDialogProps {
  open: boolean;
  onClose: () => void;
  stock: Stock;
}

export function EditMetadataDialog({ open, onClose, stock }: EditMetadataDialogProps) {
  const updateStock = useUpdateStock(stock.symbol);
  const [showPreview, setShowPreview] = useState(false);

  return (
    <Modal open={open} onClose={onClose} title="Edit metadata" className="max-w-2xl">
      <div className="space-y-2.5">
        <div>
          <label className="text-[11px] text-muted-foreground">Symbol (read-only)</label>
          <div className="mt-0.5 rounded-md border border-input bg-muted/30 px-1.5 py-1 text-xs font-mono">
            {stock.symbol}
          </div>
        </div>

        <DebouncedInput
          label="Currency"
          value={stock.currency}
          maxLength={8}
          onSave={async (next) => {
            await updateStock.mutateAsync({ currency: next.trim().toUpperCase() });
          }}
        />

        <DebouncedInput
          label="Shares outstanding"
          type="number"
          inputMode="decimal"
          step="any"
          value={stock.shares_outstanding ?? ""}
          onSave={async (next) => {
            await updateStock.mutateAsync({
              shares_outstanding: next.trim() === "" ? null : next.trim(),
            });
          }}
        />

        <DebouncedInput
          label="Category (e.g. Tech, Watchlist)"
          value={stock.category ?? ""}
          maxLength={64}
          onSave={async (next) => {
            await updateStock.mutateAsync({
              category: next.trim() === "" ? null : next.trim(),
            });
          }}
        />

        <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <input
            type="checkbox"
            checked={stock.is_financial}
            onChange={(e) => {
              void updateStock.mutateAsync({ is_financial: e.target.checked });
            }}
            className="h-3.5 w-3.5 rounded border-input"
          />
          Financial / bank — EV-based valuations (EV/EBITDA, EV/EBIT) don't apply
        </label>

        <DebouncedInput
          label='Units note (e.g. "Millions of US $ except per share data")'
          value={stock.units_note ?? ""}
          onSave={async (next) => {
            await updateStock.mutateAsync({
              units_note: next.trim() === "" ? null : next.trim(),
            });
          }}
        />

        <DebouncedInput
          label="SEC EDGAR CIK (10 digits)"
          value={stock.cik ?? ""}
          maxLength={10}
          onSave={async (next) => {
            const trimmed = next.trim();
            // Zero-pad short numeric input to the SEC canonical width so
            // EDGAR URLs work whichever way the user types it.
            const normalised =
              trimmed === ""
                ? null
                : /^\d+$/.test(trimmed)
                  ? trimmed.padStart(10, "0")
                  : trimmed;
            await updateStock.mutateAsync({ cik: normalised });
          }}
        />

        <div className="space-y-0.5">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-muted-foreground">Notes (markdown)</span>
            <button
              type="button"
              onClick={() => setShowPreview((v) => !v)}
              className="text-[10px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
            >
              {showPreview ? "Hide preview" : "Show preview"}
            </button>
          </div>
          <DebouncedTextarea
            value={stock.notes ?? ""}
            rows={6}
            onSave={async (next) => {
              await updateStock.mutateAsync({ notes: next === "" ? null : next });
            }}
            className="font-mono"
          />
          {showPreview && <MarkdownPreview source={stock.notes ?? ""} />}
        </div>
      </div>
    </Modal>
  );
}

function MarkdownPreview({ source }: { source: string }) {
  const html = renderMarkdownToHtml(source);
  return (
    <div
      className="markdown-preview rounded-md border border-border bg-background p-2 text-xs"
      // The renderer escapes input first; only a small known subset becomes HTML.
      dangerouslySetInnerHTML={{
        __html:
          html ||
          '<em class="text-muted-foreground">Nothing to preview.</em>',
      }}
    />
  );
}
