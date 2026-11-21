import { AxiosError } from 'axios';
import { describe, expect, it } from 'vitest';
import { parseApiError } from '../api/errors';
import { formatINR, timeAgo } from './format';
import { contactSchema, leadSchema, parseTags } from './schemas';

function axiosError(status: number, data: unknown) {
  return new AxiosError('fail', String(status), undefined, undefined, {
    status,
    data,
  } as never);
}

describe('parseApiError', () => {
  it('reads field errors from the backend format', () => {
    const err = axiosError(400, {
      error: { code: 'invalid', message: 'Validation failed.', details: { email: ['Taken.'] } },
    });
    expect(parseApiError(err)).toEqual({
      message: 'Taken.',
      fieldErrors: { email: 'Taken.' },
      status: 400,
    });
  });

  it('uses the backend message for non-field errors', () => {
    const err = axiosError(403, { error: { code: 'permission_denied', message: 'Nope.' } });
    expect(parseApiError(err).message).toBe('Nope.');
  });

  it('explains network failures', () => {
    expect(parseApiError(new AxiosError('Network Error')).message).toMatch(/reach the server/);
  });
});

describe('schemas', () => {
  const contact = {
    first_name: 'Asha',
    last_name: '',
    email: 'a@b.io',
    phone: '',
    company: '',
    tags: '',
  };

  it('accepts a minimal contact and rejects a bad email or phone', () => {
    expect(contactSchema.safeParse(contact).success).toBe(true);
    expect(contactSchema.safeParse({ ...contact, email: 'nope' }).success).toBe(false);
    expect(contactSchema.safeParse({ ...contact, phone: 'call me' }).success).toBe(false);
    expect(contactSchema.safeParse({ ...contact, first_name: '  ' }).success).toBe(false);
  });

  it('validates lead budgets as rupee amounts', () => {
    const lead = { contact: '1', source: 'web', status: 'new', budget: '', notes: '' };
    expect(leadSchema.safeParse(lead).success).toBe(true);
    expect(leadSchema.safeParse({ ...lead, budget: '250000.50' }).success).toBe(true);
    expect(leadSchema.safeParse({ ...lead, budget: '-5' }).success).toBe(false);
    expect(leadSchema.safeParse({ ...lead, budget: '1.234' }).success).toBe(false);
    expect(leadSchema.safeParse({ ...lead, contact: '' }).success).toBe(false);
  });

  it('parses tags: trims, lowercases, dedupes', () => {
    expect(parseTags(' VIP, trial;vip ,, ')).toEqual(['vip', 'trial']);
  });
});

describe('format', () => {
  it('formats rupees in Indian grouping', () => {
    expect(formatINR('1250000')).toBe('₹12,50,000');
    expect(formatINR(null)).toBe('—');
  });

  it('describes relative time', () => {
    const now = Date.parse('2026-11-21T12:00:00Z');
    expect(timeAgo('2026-11-18T12:00:00Z', now)).toBe('3 days ago');
    expect(timeAgo(null, now)).toBe('never');
  });
});
