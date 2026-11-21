import { Badge, type Tone } from '../../components/ui/misc';
import type { InvoiceStatus } from '../../types';

const META: Record<InvoiceStatus, { label: string; tone: Tone }> = {
  draft: { label: 'Draft', tone: 'slate' },
  sent: { label: 'Sent', tone: 'sky' },
  processing: { label: 'Processing', tone: 'amber' },
  paid: { label: 'Paid', tone: 'emerald' },
  failed: { label: 'Payment failed', tone: 'rose' },
  refunded: { label: 'Refunded', tone: 'indigo' },
};

export function InvoiceStatusBadge({ status }: { status: InvoiceStatus }) {
  const meta = META[status];
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}
