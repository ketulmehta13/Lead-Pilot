/** Razorpay Checkout.js loader + typed wrapper. TEST MODE ONLY (keys from the backend). */
import type { CheckoutOptions } from '../../types';

const SCRIPT_URL = 'https://checkout.razorpay.com/v1/checkout.js';

export interface CheckoutSuccess {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
}

interface RazorpayInstance {
  open(): void;
  on(
    event: 'payment.failed',
    cb: (r: { error: { description?: string; reason?: string } }) => void,
  ): void;
}

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => RazorpayInstance;
  }
}

let loading: Promise<void> | null = null;

export function loadCheckout(): Promise<void> {
  if (window.Razorpay) return Promise.resolve();
  loading ??= new Promise<void>((resolve, reject) => {
    const script = document.createElement('script');
    script.src = SCRIPT_URL;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => {
      loading = null;
      reject(new Error('Could not load Razorpay Checkout. Check your connection.'));
    };
    document.body.appendChild(script);
  });
  return loading;
}

/** Open Checkout. Resolves with the payment ids + signature, rejects on failure/dismiss. */
export async function openCheckout(options: CheckoutOptions): Promise<CheckoutSuccess> {
  await loadCheckout();
  return new Promise((resolve, reject) => {
    const rzp = new window.Razorpay!({
      key: options.key_id,
      order_id: options.order_id,
      amount: options.amount,
      currency: options.currency,
      name: options.name,
      description: options.description,
      prefill: options.prefill,
      notes: { invoice_id: String(options.invoice_id) },
      theme: { color: '#4f46e5' },
      handler: (response: CheckoutSuccess) => resolve(response),
      modal: { ondismiss: () => reject(new CheckoutDismissed()) },
    });
    rzp.on('payment.failed', (r) =>
      reject(new Error(r.error?.description || r.error?.reason || 'The payment failed.')),
    );
    rzp.open();
  });
}

export class CheckoutDismissed extends Error {
  constructor() {
    super('Checkout was closed before paying.');
  }
}
