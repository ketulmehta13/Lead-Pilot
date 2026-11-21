import type { FieldValues, Path, UseFormSetError } from 'react-hook-form';
import { parseApiError } from '../api/errors';

/**
 * Puts server-side validation errors onto matching form fields.
 * Returns the overall message for a toast.
 */
export function applyServerErrors<T extends FieldValues>(
  err: unknown,
  setError: UseFormSetError<T>,
  fields: readonly string[],
): string {
  const { message, fieldErrors } = parseApiError(err);
  let unmatched = false;
  for (const [field, msg] of Object.entries(fieldErrors)) {
    if (fields.includes(field)) setError(field as Path<T>, { type: 'server', message: msg });
    else unmatched = true;
  }
  return Object.keys(fieldErrors).length && !unmatched
    ? 'Please fix the highlighted fields.'
    : message;
}

/** '' -> null, for optional numbers/dates/foreign keys sent to the API. */
export function emptyToNull<T extends string | number>(value: T | '' | undefined): T | null {
  return value === '' || value === undefined ? null : value;
}
