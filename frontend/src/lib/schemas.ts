import { z } from 'zod';

/** Form schemas shared by components and unit tests. */

export const contactSchema = z.object({
  first_name: z.string().trim().min(1, 'First name is required').max(100),
  last_name: z.string().trim().max(100),
  email: z.email('Enter a valid email'),
  phone: z
    .string()
    .trim()
    .max(30)
    .regex(/^[\d\s()+-]*$/, 'Only digits, spaces and + ( ) -'),
  company: z.string(),
  tags: z.string().max(400),
});

export function parseTags(raw: string): string[] {
  return [
    ...new Set(
      raw
        .split(/[,;]/)
        .map((t) => t.trim().toLowerCase())
        .filter(Boolean),
    ),
  ];
}

export const leadSchema = z.object({
  contact: z.string().min(1, 'Choose a contact'),
  source: z.string().min(1),
  status: z.string().min(1),
  budget: z
    .string()
    .trim()
    .refine((v) => v === '' || (/^\d+(\.\d{1,2})?$/.test(v) && Number(v) <= 9_999_999_999), {
      message: 'Enter an amount in rupees, e.g. 250000',
    }),
  notes: z.string().max(5000),
});
