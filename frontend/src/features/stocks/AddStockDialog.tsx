import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Modal } from "@/components/Modal";
import { ApiError } from "@/lib/api";
import { useCreateStock } from "@/lib/stocks";
import { useToast } from "@/stores/toast";

interface AddStockDialogProps {
  open: boolean;
  onClose: () => void;
}

export function AddStockDialog({ open, onClose }: AddStockDialogProps) {
  const navigate = useNavigate();
  const toast = useToast();
  const createStock = useCreateStock();

  const [symbol, setSymbol] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [shares, setShares] = useState("");
  const [category, setCategory] = useState("");
  const [isFinancial, setIsFinancial] = useState(false);
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setSymbol("");
    setCurrency("USD");
    setShares("");
    setCategory("");
    setIsFinancial(false);
    setNotes("");
    setError(null);
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!symbol.trim()) {
      setError("Symbol is required.");
      return;
    }
    if (!currency.trim()) {
      setError("Currency is required.");
      return;
    }

    try {
      const created = await createStock.mutateAsync({
        symbol: symbol.trim(),
        currency: currency.trim().toUpperCase(),
        shares_outstanding: shares.trim() === "" ? null : shares.trim(),
        category: category.trim() === "" ? null : category.trim(),
        is_financial: isFinancial,
        notes: notes.trim() === "" ? null : notes,
      });
      reset();
      onClose();
      toast.show(`${created.symbol} created`, { tone: "success" });
      navigate(`/stocks/${encodeURIComponent(created.symbol)}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(typeof err.detail === "string" ? err.detail : "Symbol already exists.");
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Could not create stock.");
      }
    }
  }

  return (
    <Modal
      open={open}
      onClose={() => {
        if (!createStock.isPending) {
          reset();
          onClose();
        }
      }}
      title="Add Stock"
    >
      <form onSubmit={handleSubmit} className="space-y-2">
        <FieldRow label="Symbol" htmlFor="add-symbol">
          <input
            id="add-symbol"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            autoFocus
            required
            maxLength={32}
            placeholder="AAPL"
            className="h-7 w-full rounded-md border border-input bg-background px-1.5 text-xs uppercase focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </FieldRow>
        <FieldRow label="Currency" htmlFor="add-currency">
          <input
            id="add-currency"
            value={currency}
            onChange={(e) => setCurrency(e.target.value.toUpperCase())}
            required
            maxLength={8}
            placeholder="USD"
            className="h-7 w-full rounded-md border border-input bg-background px-1.5 text-xs uppercase focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </FieldRow>
        <FieldRow label="Shares outstanding (optional)" htmlFor="add-shares">
          <input
            id="add-shares"
            value={shares}
            onChange={(e) => setShares(e.target.value)}
            type="number"
            inputMode="decimal"
            step="any"
            placeholder="15500000000"
            className="h-7 w-full rounded-md border border-input bg-background px-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </FieldRow>
        <FieldRow label="Category (optional)" htmlFor="add-category">
          <input
            id="add-category"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            maxLength={64}
            placeholder="e.g. Tech, Watchlist, BIST"
            className="h-7 w-full rounded-md border border-input bg-background px-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </FieldRow>
        <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <input
            type="checkbox"
            checked={isFinancial}
            onChange={(e) => setIsFinancial(e.target.checked)}
            className="h-3.5 w-3.5 rounded border-input"
          />
          Financial / bank (EV-based valuations don't apply)
        </label>
        <FieldRow label="Notes (optional, markdown)" htmlFor="add-notes">
          <textarea
            id="add-notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            placeholder="## Thesis"
            className="w-full rounded-md border border-input bg-background px-1.5 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </FieldRow>

        {error && (
          <p role="alert" className="text-[11px] text-destructive">
            {error}
          </p>
        )}

        <div className="flex justify-end gap-1.5 pt-1">
          <button
            type="button"
            onClick={() => {
              reset();
              onClose();
            }}
            disabled={createStock.isPending}
            className="rounded-md border border-border bg-secondary px-2.5 py-1 text-[11px] text-secondary-foreground hover:bg-accent disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={createStock.isPending}
            className="rounded-md bg-primary px-2.5 py-1 text-[11px] font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
          >
            {createStock.isPending ? "Creating…" : "Create stock"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function FieldRow({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <label htmlFor={htmlFor} className="text-[11px] text-muted-foreground">
        {label}
      </label>
      {children}
    </div>
  );
}
