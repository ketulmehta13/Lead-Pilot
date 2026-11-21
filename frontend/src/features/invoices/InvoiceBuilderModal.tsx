import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { invoicesApi } from '../../api/billing';
import { dealsApi } from '../../api/crm';
import { parseApiError } from '../../api/errors';
import { useToast } from '../../components/Toast';
import { Button } from '../../components/ui/Button';
import { controlClass } from '../../components/ui/Field';
import { Modal } from '../../components/ui/Modal';
import { formatINR } from '../../lib/format';
import type { Deal, InvoiceItem } from '../../types';

const GST = 0.18;

function lineTotal(item: InvoiceItem) {
  const qty = Number(item.quantity);
  const price = Number(item.unit_price);
  return Number.isFinite(qty) && Number.isFinite(price) ? qty * price : 0;
}

/** Build an invoice from a Won deal: editable line items, live subtotal / GST / total. */
export function InvoiceBuilderModal({
  initialDealId,
  onClose,
}: {
  initialDealId?: number | null;
  onClose: () => void;
}) {
  const toast = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [dealId, setDealId] = useState<number | null>(initialDealId ?? null);
  // null = not edited yet: use one line for the deal at its value.
  const [edited, setEdited] = useState<InvoiceItem[] | null>(null);
  const [dueInDays, setDueInDays] = useState('7');
  const [notes, setNotes] = useState('');

  const deals = useQuery({
    queryKey: [dealsApi.key, 'won-for-invoice'],
    queryFn: () => dealsApi.list({ stage: 'won', page_size: 100, ordering: '-closed_at' }),
  });
  const wonDeals: Deal[] = deals.data?.results ?? [];
  const deal = wonDeals.find((d) => d.id === dealId) ?? null;

  const items: InvoiceItem[] =
    edited ??
    (deal
      ? [{ description: deal.title, quantity: '1', unit_price: String(Number(deal.value)) }]
      : []);
  const setItems = (next: (all: InvoiceItem[]) => InvoiceItem[]) => setEdited(next(items));

  const subtotal = items.reduce((sum, i) => sum + lineTotal(i), 0);
  const tax = Math.round(subtotal * GST * 100) / 100;
  const valid =
    deal !== null &&
    items.length > 0 &&
    items.every(
      (i) => i.description.trim() && Number(i.quantity) > 0 && Number(i.unit_price) >= 0,
    ) &&
    subtotal > 0;

  const create = useMutation({
    mutationFn: () =>
      invoicesApi.create({
        deal: dealId!,
        items,
        due_in_days: Number(dueInDays) || 7,
        notes,
      }),
    onSuccess: (invoice) => {
      queryClient.invalidateQueries({ queryKey: [invoicesApi.key] });
      toast.success(`Created invoice ${invoice.number}`);
      onClose();
      navigate(`/invoices/${invoice.id}`);
    },
    onError: (err) => toast.error(parseApiError(err).message),
  });

  const update = (index: number, patch: Partial<InvoiceItem>) =>
    setItems((all) => all.map((item, i) => (i === index ? { ...item, ...patch } : item)));

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title="New invoice"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={!valid} loading={create.isPending} onClick={() => create.mutate()}>
            Create invoice
          </Button>
        </>
      }
    >
      <div className="space-y-4 text-sm">
        <label className="block">
          <span className="mb-1 block font-medium">Won deal</span>
          <select
            value={dealId ?? ''}
            onChange={(e) => {
              setDealId(e.target.value ? Number(e.target.value) : null);
              setEdited(null);
            }}
            className={controlClass}
          >
            <option value="">{deals.isLoading ? 'Loading…' : 'Choose a won deal'}</option>
            {wonDeals.map((d) => (
              <option key={d.id} value={d.id}>
                {d.title} · {d.company_name ?? d.contact_name} · {formatINR(d.value)}
              </option>
            ))}
          </select>
          {!deals.isLoading && wonDeals.length === 0 && (
            <span className="mt-1 block text-xs text-slate-500">
              No won deals yet. Move a deal to Won on the pipeline first.
            </span>
          )}
        </label>

        {deal && (
          <>
            <table className="w-full text-left">
              <thead className="text-xs text-slate-500">
                <tr>
                  <th className="pb-1 font-medium">Description</th>
                  <th className="w-20 pb-1 font-medium">Qty</th>
                  <th className="w-32 pb-1 font-medium">Unit price (₹)</th>
                  <th className="w-28 pb-1 text-right font-medium">Amount</th>
                  <th className="w-8" />
                </tr>
              </thead>
              <tbody>
                {items.map((item, i) => (
                  <tr key={i}>
                    <td className="py-1 pr-2">
                      <input
                        aria-label={`Line ${i + 1} description`}
                        value={item.description}
                        maxLength={200}
                        onChange={(e) => update(i, { description: e.target.value })}
                        className={controlClass}
                      />
                    </td>
                    <td className="py-1 pr-2">
                      <input
                        aria-label={`Line ${i + 1} quantity`}
                        inputMode="decimal"
                        value={item.quantity}
                        onChange={(e) => update(i, { quantity: e.target.value })}
                        className={controlClass}
                      />
                    </td>
                    <td className="py-1 pr-2">
                      <input
                        aria-label={`Line ${i + 1} unit price`}
                        inputMode="decimal"
                        value={item.unit_price}
                        onChange={(e) => update(i, { unit_price: e.target.value })}
                        className={controlClass}
                      />
                    </td>
                    <td className="py-1 text-right tabular-nums">{formatINR(lineTotal(item))}</td>
                    <td className="py-1 pl-1">
                      <button
                        type="button"
                        aria-label={`Remove line ${i + 1}`}
                        disabled={items.length === 1}
                        onClick={() => setItems((all) => all.filter((_, j) => j !== i))}
                        className="rounded p-1 text-slate-400 hover:text-rose-500 disabled:opacity-30"
                      >
                        <Trash2 className="size-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Button
              variant="ghost"
              size="sm"
              onClick={() =>
                setItems((all) => [...all, { description: '', quantity: '1', unit_price: '0' }])
              }
            >
              <Plus className="size-3.5" /> Add line
            </Button>

            <dl className="ml-auto w-64 space-y-1 tabular-nums">
              <div className="flex justify-between">
                <dt className="text-slate-500">Subtotal</dt>
                <dd>{formatINR(subtotal)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">GST 18%</dt>
                <dd>{formatINR(tax)}</dd>
              </div>
              <div className="flex justify-between border-t border-slate-200 pt-1 font-semibold dark:border-slate-700">
                <dt>Total</dt>
                <dd>{formatINR(subtotal + tax)}</dd>
              </div>
            </dl>

            <div className="grid gap-3 sm:grid-cols-3">
              <label className="block">
                <span className="mb-1 block font-medium">Due in (days)</span>
                <input
                  inputMode="numeric"
                  value={dueInDays}
                  onChange={(e) => setDueInDays(e.target.value)}
                  className={controlClass}
                />
              </label>
              <label className="block sm:col-span-2">
                <span className="mb-1 block font-medium">Notes</span>
                <input
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  className={controlClass}
                />
              </label>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
