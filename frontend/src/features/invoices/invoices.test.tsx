import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { invoicesApi } from '../../api/billing';
import { dealsApi } from '../../api/crm';
import { ToastProvider } from '../../components/Toast';
import type { Invoice } from '../../types';
import { InvoiceBuilderModal } from './InvoiceBuilderModal';
import { InvoiceDetailPage } from './InvoiceDetailPage';

vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ hasRole: (...roles: string[]) => roles.includes('sales') }),
}));
vi.mock('../../api/billing', () => ({
  invoicesApi: {
    key: 'invoices',
    get: vi.fn(),
    create: vi.fn(),
    createOrder: vi.fn(),
    verify: vi.fn(),
    paymentLink: vi.fn(),
    refund: vi.fn(),
    config: vi.fn(),
  },
}));
vi.mock('../../api/crm', () => ({
  dealsApi: { key: 'deals', list: vi.fn() },
}));

const api = vi.mocked(invoicesApi);

const invoice: Invoice = {
  id: 1,
  number: 'LP-2026-00007',
  deal: 3,
  deal_title: 'Annual licence',
  contact: 9,
  contact_name: 'Asha Rao',
  contact_email: 'asha@acme.io',
  company_name: 'Acme',
  status: 'sent',
  currency: 'INR',
  items: [
    {
      id: 1,
      description: 'Annual licence',
      quantity: '1.00',
      unit_price: '499.50',
      amount: '499.50',
    },
  ],
  subtotal: '499.50',
  tax_rate: '18.00',
  tax: '89.91',
  total: '589.41',
  due_date: '2026-12-01',
  notes: '',
  razorpay_order_id: '',
  payment_link_url: '',
  paid_at: null,
  payments: [],
  owner: 1,
  owner_name: 'Priya',
  created_at: '2026-11-20T10:00:00Z',
  updated_at: '2026-11-20T10:00:00Z',
};

function renderDetail() {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ToastProvider>
        <MemoryRouter initialEntries={['/invoices/1']}>
          <Routes>
            <Route path="/invoices/:id" element={<InvoiceDetailPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  api.config.mockResolvedValue({ configured: true, key_id: 'rzp_test_x', test_mode: true });
  delete (window as { Razorpay?: unknown }).Razorpay;
});

describe('Invoice detail', () => {
  it('shows totals with GST and pays through Checkout, then confirms via webhook', async () => {
    api.get
      .mockResolvedValueOnce(invoice)
      .mockResolvedValue({ ...invoice, status: 'paid', paid_at: '2026-11-21T10:00:00Z' });
    api.createOrder.mockResolvedValue({
      key_id: 'rzp_test_x',
      order_id: 'order_1',
      amount: 58941,
      currency: 'INR',
      name: 'LeadPilot',
      description: 'Invoice LP-2026-00007',
      invoice_id: 1,
      prefill: { name: 'Asha Rao', email: 'asha@acme.io', contact: '' },
    });
    api.verify.mockResolvedValue({ ...invoice, status: 'processing' });
    // Stub Checkout.js: succeed immediately with ids + signature.
    const opened: Record<string, unknown>[] = [];
    window.Razorpay = class {
      constructor(private options: Record<string, unknown>) {
        opened.push(options);
      }
      on() {}
      open() {
        (this.options.handler as (r: unknown) => void)({
          razorpay_payment_id: 'pay_1',
          razorpay_order_id: 'order_1',
          razorpay_signature: 'sig',
        });
      }
    } as unknown as typeof window.Razorpay;

    const user = userEvent.setup();
    renderDetail();
    expect(await screen.findByText('LP-2026-00007')).toBeInTheDocument();
    expect(screen.getByText('GST 18%')).toBeInTheDocument();
    expect(screen.getByText('₹589')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /pay now/i }));
    expect(opened[0]).toMatchObject({ key: 'rzp_test_x', order_id: 'order_1', amount: 58941 });
    expect(JSON.stringify(opened[0])).not.toMatch(/secret/i);
    expect(api.verify).toHaveBeenCalledWith({
      razorpay_payment_id: 'pay_1',
      razorpay_order_id: 'order_1',
      razorpay_signature: 'sig',
    });
    expect(await screen.findByText('Payment received', {}, { timeout: 8000 })).toBeInTheDocument();
  });

  it('shows a failure screen when the payment fails', async () => {
    api.get.mockResolvedValue(invoice);
    api.createOrder.mockResolvedValue({
      key_id: 'k',
      order_id: 'o',
      amount: 1,
      currency: 'INR',
      name: 'n',
      description: 'd',
      invoice_id: 1,
      prefill: { name: '', email: '', contact: '' },
    });
    window.Razorpay = class {
      private failed?: (r: { error: { description: string } }) => void;
      on(_: string, cb: (r: { error: { description: string } }) => void) {
        this.failed = cb;
      }
      open() {
        this.failed?.({ error: { description: 'Card declined by bank' } });
      }
    } as unknown as typeof window.Razorpay;
    const user = userEvent.setup();
    renderDetail();
    await user.click(await screen.findByRole('button', { name: /pay now/i }));
    expect(await screen.findByText('Payment failed')).toBeInTheDocument();
    expect(screen.getByText('Card declined by bank')).toBeInTheDocument();
  });

  it('disables payments until Razorpay test keys are configured', async () => {
    api.config.mockResolvedValue({ configured: false, key_id: '', test_mode: true });
    api.get.mockResolvedValue(invoice);
    renderDetail();
    expect(await screen.findByText(/payments are off/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /pay now/i })).toBeDisabled();
  });
});

describe('Invoice builder', () => {
  it('starts from the won deal and computes GST live', async () => {
    vi.mocked(dealsApi.list).mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 3,
          title: 'Annual licence',
          value: '1000.00',
          company_name: 'Acme',
          contact_name: 'Asha',
        },
      ],
    } as never);
    const user = userEvent.setup();
    render(
      <QueryClientProvider client={new QueryClient()}>
        <ToastProvider>
          <MemoryRouter>
            <InvoiceBuilderModal initialDealId={3} onClose={() => {}} />
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    expect(await screen.findByDisplayValue('Annual licence')).toBeInTheDocument();
    expect(screen.getByText('₹1,180')).toBeInTheDocument(); // 1000 + 18% GST
    const qty = screen.getByLabelText('Line 1 quantity');
    await user.clear(qty);
    await user.type(qty, '2');
    expect(screen.getByText('₹2,360')).toBeInTheDocument();
  });
});
