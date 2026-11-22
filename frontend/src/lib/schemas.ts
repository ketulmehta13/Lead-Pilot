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

const rupees = (required: boolean) =>
  z
    .string()
    .trim()
    .refine((v) => (required ? v !== '' : true), { message: 'Enter an amount' })
    .refine((v) => v === '' || (/^\d+(\.\d{1,2})?$/.test(v) && Number(v) <= 9_999_999_999), {
      message: 'Enter an amount in rupees, e.g. 250000',
    });

export const dealSchema = z.object({
  title: z.string().trim().min(1, 'Title is required').max(200),
  contact: z.string().min(1, 'Choose a contact'),
  value: rupees(true),
  stage: z.string().min(1),
  expected_close_date: z.string(),
  probability: z
    .string()
    .trim()
    .refine((v) => v === '' || (/^\d+$/.test(v) && Number(v) <= 100), {
      message: 'Whole number from 0 to 100',
    }),
});

export const convertLeadSchema = z.object({
  title: z.string().trim().max(200),
  value: rupees(false),
  stage: z.string().min(1),
  expected_close_date: z.string(),
});

export const ticketSchema = z.object({
  subject: z.string().trim().min(1, 'Subject is required').max(200),
  description: z.string().trim().min(1, 'Describe the problem').max(10_000),
  contact: z.string().min(1, 'Choose the customer'),
  priority: z.string(),
});

// --- Settings ---------------------------------------------------------------------------

export const profileSchema = z.object({
  first_name: z.string().trim().max(150),
  last_name: z.string().trim().max(150),
  email: z.email('Enter a valid email'),
});

const newPassword = z
  .string()
  .min(8, 'Use at least 8 characters')
  .max(128)
  .refine((p) => !/^\d+$/.test(p), 'Use letters too, not only numbers');

export const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, 'Enter your current password'),
    new_password: newPassword,
    confirm: z.string(),
  })
  .refine((v) => v.new_password === v.confirm, {
    path: ['confirm'],
    message: 'Passwords do not match',
  })
  .refine((v) => v.new_password !== v.current_password, {
    path: ['new_password'],
    message: 'Choose a different password',
  });

export const teamMemberSchema = z.object({
  username: z
    .string()
    .trim()
    .min(3, 'At least 3 characters')
    .max(150)
    .regex(/^[\w.@+-]+$/, 'Letters, digits and . @ + - _ only'),
  first_name: z.string().trim().max(150),
  last_name: z.string().trim().max(150),
  email: z.email('Enter a valid email'),
  role: z.enum(['admin', 'sales', 'support']),
  password: z.string(),
});

/** New users need a password; editing an existing user doesn't touch it. */
export const newTeamMemberSchema = teamMemberSchema.extend({ password: newPassword });

export const resetPasswordSchema = z
  .object({ password: newPassword, confirm: z.string() })
  .refine((v) => v.password === v.confirm, {
    path: ['confirm'],
    message: 'Passwords do not match',
  });
