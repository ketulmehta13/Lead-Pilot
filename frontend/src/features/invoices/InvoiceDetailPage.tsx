import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  Check,
  CheckCircle2,
  Copy,
  CreditCard,
  Link2,
  Loader2,
  RotateCcw,
  XCircle,
} from 'lucide-react';
import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { analyticsApi } from '../../api/analytics';
import { invoicesApi } from '../../api/billing';
import { parseApiError } from '../../api/errors';
import { useToast } from '../../components/Toast';
import { Button } from '../../components/ui/Button';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { Badge } from '../../components/ui/misc';
import { Spinner } from '../../components/ui/Spinner';
import { formatDate, formatDateTime, formatINR } from '../../lib/format';
import type { Invoice, PaymentRecord } from '../../types';
import { useAuth } from '../auth/AuthContext';
import { CheckoutDismissed, openCheckout } from './checkout';
import { InvoiceStatusBadge } from './InvoiceStatusBadge';

type Outcome = { kind: 'success' } | { kind: 'failure'; message: string } | null;

export function InvoiceDetailPage() {
  const id = Number(useParams().id);
  const { hasRole } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [outcome, setOutcome] = useState<Outcome>(null);
  const [copied, setCopied] = useState(false);
  const [refunding, setRefunding] = useState<PaymentRecord | null>(null);

  const config = useQuery({ queryKey: [invoicesApi.key, 'config'], queryFn: invoicesApi.config });
  const invoice = useQuery({
    queryKey: [invoicesApi.key, 'detail', id],
    queryFn: () => invoicesApi.get(id),
    enabled: Number.isFinite(id),
    // After Checkout succeeds the webhook confirms the payment: poll until it's "paid".
    refetchInterval: (q) =>
      outcome?.kind === 'success' && q.state.data?.status !== 'paid' ? 2000 : false,
  });

  const refresh = (inv?: Invoice) => {
    if (inv) queryClient.setQueryData([invoicesApi.key, 'detail', id], inv);
    queryClient.invalidateQueries({ queryKey: [invoicesApi.key] });
    queryClient.invalidateQueries({ queryKey: [analyticsApi.key] });
  };

  const pay = useMutation({
    mutationFn: async () => {
      const options = await invoicesApi.createOrder(id);
      const result = await openCheckout(options);
      return invoicesApi.verify(result);
    },
    onSuccess: (inv) => {
      setOutcome({ kind: 'success' });
      refresh(inv);
    },
    onError: (err) => {
      if (err instanceof CheckoutDismissed) return;
      setOutcome({ kind: 'failure', message: parseApiError(err).message });
      refresh();
    },
  });

  const link = useMutation({
    mutationFn: () => invoicesApi.paymentLink(id),
    onSuccess: (inv) => {
      refresh(inv);
      toast.success('Payment link created and emailed to the customer');
    },
    onError: (err) => toast.error(parseApiError(err).message),
  });

  const refund = useMutation({
    mutationFn: (p: PaymentRecord) => invoicesApi.refund(p.id),
    onSuccess: () => {
      setRefunding(null);
      refresh();
      queryClient.invalidateQueries({ queryKey: [invoicesApi.key, 'detail', id] });
      toast.success('Refund issued');
    },
    onError: (err) => toast.error(parseApiError(err).message),
  });

  if (invoice.isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner label="Loading invoice" />
      </div>
    );
  }
  if (invoice.isError || !invoice.data) {
    return (
      <div className="py-20 text-center">
        <p className="font-medium">{parseApiError(invoice.error).message}</p>
        <Link to="/invoices" className="mt-3 inline-block text-indigo-600 hover:underline">
          Back to invoices
        </Link>
      </div>
    );
  }

  const inv = invoice.data;
  const payable = !['paid', 'refunded'].includes(inv.status);
  const paymentsReady = config.data?.configured ?? false;

  return (
    <section>
      <Link
        to="/invoices"
        className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
      >
        <ArrowLeft className="size-4" /> Invoices
      </Link>

      {outcome?.kind === 'success' && (
        <div
          role="status"
          className="mb-4 flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4 dark:border-emerald-500/30 dark:bg-emerald-500/10"
        >
          {inv.status === 'paid' ? (
            <CheckCircle2 className="size-6 shrink-0 text-emerald-600" aria-hidden />
          ) : (
            <Loader2 className="size-6 shrink-0 animate-spin text-emerald-600" aria-hidden />
          )}
          <div>
            <p className="font-semibold text-emerald-900 dark:text-emerald-200">
              {inv.status === 'paid' ? 'Payment received' : 'Payment successful, confirming…'}
            </p>
            <p className="text-sm text-emerald-800 dark:text-emerald-300">
              {inv.status === 'paid'
                ? `${inv.number} is paid. The deal is marked Won and the dashboard is updated.`
                : 'Razorpay confirms the payment by webhook. This usually takes a few seconds.'}
            </p>
          </div>
        </div>
      )}
      {outcome?.kind === 'failure' && (
        <div
          role="alert"
          className="mb-4 flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 dark:border-rose-500/30 dark:bg-rose-500/10"
        >
          <XCircle className="size-6 shrink-0 text-rose-600" aria-hidden />
          <div className="flex-1">
            <p className="font-semibold text-rose-900 dark:text-rose-200">Payment failed</p>
            <p className="text-sm text-rose-800 dark:text-rose-300">{outcome.message}</p>
          </div>
          <Button size="sm" variant="secondary" onClick={() => setOutcome(null)}>
            Dismiss
          </Button>
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-semibold tabular-nums">{inv.number}</h1>
              <InvoiceStatusBadge status={inv.status} />
            </div>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
              <Link to={`/contacts/${inv.contact}`} className="font-medium hover:underline">
                {inv.contact_name}
              </Link>
              {inv.company_name ? ` · ${inv.company_name}` : ''} · {inv.contact_email}
            </p>
            <p className="mt-0.5 text-xs text-slate-500">
              Deal: {inv.deal_title} · issued {formatDate(inv.created_at)}
              {inv.due_date ? ` · due ${formatDate(inv.due_date)}` : ''}
              {inv.paid_at ? ` · paid ${formatDateTime(inv.paid_at)}` : ''}
            </p>
          </div>
          {payable && (
            <div className="flex flex-wrap gap-2">
              <Button
                variant="secondary"
                loading={link.isPending}
                disabled={!paymentsReady || Boolean(inv.payment_link_url)}
                onClick={() => link.mutate()}
              >
                <Link2 className="size-4" />{' '}
                {inv.payment_link_url ? 'Link sent' : 'Send payment link'}
              </Button>
              <Button
                loading={pay.isPending}
                disabled={!paymentsReady}
                onClick={() => pay.mutate()}
              >
                <CreditCard className="size-4" /> Pay Now · {formatINR(inv.total)}
              </Button>
            </div>
          )}
        </div>

        {config.data && !config.data.configured && payable && (
          <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:bg-amber-500/10 dark:text-amber-200">
            Payments are off: add Razorpay TEST keys (<code>RAZORPAY_KEY_ID</code>,{' '}
            <code>RAZORPAY_KEY_SECRET</code>, <code>RAZORPAY_WEBHOOK_SECRET</code>) to the backend
            .env.
          </p>
        )}
        {inv.payment_link_url && (
          <div className="mt-3 flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2 text-sm dark:bg-slate-800">
            <Link2 className="size-4 text-slate-500" aria-hidden />
            <a
              href={inv.payment_link_url}
              target="_blank"
              rel="noreferrer"
              className="truncate text-indigo-600 hover:underline dark:text-indigo-400"
            >
              {inv.payment_link_url}
            </a>
            <button
              type="button"
              className="ml-auto inline-flex items-center gap-1 text-xs text-slate-500 hover:text-indigo-600"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(inv.payment_link_url);
                  setCopied(true);
                } catch {
                  setCopied(false);
                }
              }}
            >
              {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
        )}

        <table className="mt-5 w-full text-left text-sm">
          <thead className="border-b border-slate-200 text-xs text-slate-500 dark:border-slate-700">
            <tr>
              <th className="py-2 font-medium">Description</th>
              <th className="py-2 text-right font-medium">Qty</th>
              <th className="py-2 text-right font-medium">Unit price</th>
              <th className="py-2 text-right font-medium">Amount</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {inv.items.map((item) => (
              <tr key={item.id}>
                <td className="py-2">{item.description}</td>
                <td className="py-2 text-right tabular-nums">{Number(item.quantity)}</td>
                <td className="py-2 text-right tabular-nums">{formatINR(item.unit_price)}</td>
                <td className="py-2 text-right tabular-nums">{formatINR(item.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <dl className="mt-3 ml-auto w-64 space-y-1 text-sm tabular-nums">
          <div className="flex justify-between">
            <dt className="text-slate-500">Subtotal</dt>
            <dd>{formatINR(inv.subtotal)}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">GST {Number(inv.tax_rate)}%</dt>
            <dd>{formatINR(inv.tax)}</dd>
          </div>
          <div className="flex justify-between border-t border-slate-200 pt-1 text-base font-semibold dark:border-slate-700">
            <dt>Total</dt>
            <dd>{formatINR(inv.total)}</dd>
          </div>
        </dl>
        {inv.notes && (
          <p className="mt-4 text-sm text-slate-600 dark:text-slate-300">Notes: {inv.notes}</p>
        )}
      </div>

      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="font-semibold">Payment history</h2>
        {inv.payments.length === 0 ? (
          <p className="mt-2 text-sm text-slate-500">No payments yet.</p>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-slate-500">
                <tr>
                  <th className="py-1.5 font-medium">Payment</th>
                  <th className="py-1.5 font-medium">Method</th>
                  <th className="py-1.5 font-medium">Status</th>
                  <th className="py-1.5 text-right font-medium">Amount</th>
                  <th className="py-1.5 font-medium">Date</th>
                  {hasRole('admin') && <th />}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {inv.payments.map((p) => (
                  <tr key={p.id}>
                    <td className="py-2 font-mono text-xs">{p.razorpay_payment_id}</td>
                    <td className="py-2 capitalize">{p.method || '—'}</td>
                    <td className="py-2">
                      <Badge
                        tone={
                          p.status === 'captured'
                            ? 'emerald'
                            : p.status === 'failed'
                              ? 'rose'
                              : p.status === 'refunded'
                                ? 'indigo'
                                : 'amber'
                        }
                      >
                        {p.status}
                      </Badge>
                      {Number(p.refunded_amount) > 0 && p.status !== 'refunded' && (
                        <span className="ml-1 text-xs text-slate-500">
                          ({formatINR(p.refunded_amount)} refunded)
                        </span>
                      )}
                    </td>
                    <td className="py-2 text-right tabular-nums">{formatINR(p.amount)}</td>
                    <td className="py-2 text-slate-600 dark:text-slate-400">
                      {formatDateTime(p.created_at)}
                    </td>
                    {hasRole('admin') && (
                      <td className="py-2 text-right">
                        {p.status === 'captured' && (
                          <Button size="sm" variant="ghost" onClick={() => setRefunding(p)}>
                            <RotateCcw className="size-3.5" /> Refund
                          </Button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={refunding !== null}
        title="Refund this payment?"
        message={`Refund ${formatINR(refunding?.amount)} to the customer through Razorpay (test mode). This can't be undone.`}
        confirmLabel="Refund"
        loading={refund.isPending}
        onConfirm={() => refunding && refund.mutate(refunding)}
        onCancel={() => setRefunding(null)}
      />
    </section>
  );
}
