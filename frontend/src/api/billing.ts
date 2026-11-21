import type { CheckoutOptions, Invoice, InvoiceItem, PaymentRecord } from '../types';
import { api } from './client';
import { resource } from './crm';

export const invoicesApi = {
  ...resource<
    Invoice,
    { deal: number; items?: InvoiceItem[]; due_in_days?: number; notes?: string }
  >('invoices', '/api/billing'),
  async createOrder(id: number): Promise<CheckoutOptions> {
    const { data } = await api.post<CheckoutOptions>(`/api/billing/invoices/${id}/create-order/`);
    return data;
  },
  async paymentLink(id: number): Promise<Invoice> {
    const { data } = await api.post<Invoice>(`/api/billing/invoices/${id}/payment-link/`);
    return data;
  },
  async verify(input: {
    razorpay_order_id: string;
    razorpay_payment_id: string;
    razorpay_signature: string;
  }): Promise<Invoice> {
    const { data } = await api.post<Invoice>('/api/billing/verify/', input);
    return data;
  },
  async refund(paymentId: number, amount?: string): Promise<PaymentRecord> {
    const { data } = await api.post<PaymentRecord>(
      `/api/billing/payments/${paymentId}/refund/`,
      amount ? { amount } : {},
    );
    return data;
  },
  async config(): Promise<{ configured: boolean; key_id: string; test_mode: boolean }> {
    const { data } = await api.get('/api/billing/config/');
    return data;
  },
};
