import type { Tone } from '../components/ui/misc';
import type { TicketPriority, TicketStatus } from '../types';

export interface Option {
  value: string;
  label: string;
}

export const INDUSTRY_OPTIONS: Option[] = [
  { value: 'technology', label: 'Technology' },
  { value: 'finance', label: 'Finance' },
  { value: 'healthcare', label: 'Healthcare' },
  { value: 'retail', label: 'Retail' },
  { value: 'manufacturing', label: 'Manufacturing' },
  { value: 'education', label: 'Education' },
  { value: 'real_estate', label: 'Real estate' },
  { value: 'hospitality', label: 'Hospitality' },
  { value: 'other', label: 'Other' },
];

export const SIZE_OPTIONS: Option[] = [
  { value: '1-10', label: '1–10' },
  { value: '11-50', label: '11–50' },
  { value: '51-200', label: '51–200' },
  { value: '201-1000', label: '201–1000' },
  { value: '1000+', label: '1000+' },
];

export const LEAD_SOURCE_OPTIONS: Option[] = [
  { value: 'web', label: 'Web' },
  { value: 'referral', label: 'Referral' },
  { value: 'ads', label: 'Ads' },
  { value: 'event', label: 'Event' },
  { value: 'cold', label: 'Cold outreach' },
];

export const LEAD_STATUS_OPTIONS: Option[] = [
  { value: 'new', label: 'New' },
  { value: 'contacted', label: 'Contacted' },
  { value: 'qualified', label: 'Qualified' },
  { value: 'unqualified', label: 'Unqualified' },
  { value: 'converted', label: 'Converted' },
];

export const LEAD_STATUS_TONE: Record<string, Tone> = {
  new: 'sky',
  contacted: 'indigo',
  qualified: 'emerald',
  unqualified: 'slate',
  converted: 'amber',
};

export const ACTIVITY_TYPE_OPTIONS: Option[] = [
  { value: 'call', label: 'Call' },
  { value: 'email', label: 'Email' },
  { value: 'meeting', label: 'Meeting' },
  { value: 'note', label: 'Note' },
];

export const TASK_STATUS_OPTIONS: Option[] = [
  { value: 'todo', label: 'To do' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'done', label: 'Done' },
];

export const TASK_PRIORITY_OPTIONS: Option[] = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
];

export const PRIORITY_TONE: Record<string, Tone> = { low: 'slate', medium: 'sky', high: 'rose' };

export function labelOf(options: Option[], value: string | null | undefined): string {
  return options.find((o) => o.value === value)?.label ?? value ?? '—';
}

export const DEAL_STAGE_OPTIONS: Option[] = [
  { value: 'new', label: 'New' },
  { value: 'qualified', label: 'Qualified' },
  { value: 'proposal', label: 'Proposal' },
  { value: 'negotiation', label: 'Negotiation' },
  { value: 'won', label: 'Won' },
  { value: 'lost', label: 'Lost' },
];
export const OPEN_DEAL_STAGE_OPTIONS = DEAL_STAGE_OPTIONS.filter(
  (o) => o.value !== 'won' && o.value !== 'lost',
);

export const TICKET_STATUS_OPTIONS: { value: TicketStatus; label: string }[] = [
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'closed', label: 'Closed' },
];

export const TICKET_PRIORITY_OPTIONS: { value: TicketPriority; label: string }[] = [
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
];
