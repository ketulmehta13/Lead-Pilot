import { isAxiosError } from 'axios';

/** Backend error shape: {"error": {"code", "message", "details"}} (see common/exceptions.py). */
interface ApiErrorBody {
  error?: { code?: string; message?: string; details?: unknown };
}

export interface ParsedApiError {
  message: string;
  /** field name -> first message, for validation errors */
  fieldErrors: Record<string, string>;
  status?: number;
}

function firstMessage(value: unknown): string | null {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return firstMessage(value[0]);
  return null;
}

export function parseApiError(err: unknown): ParsedApiError {
  if (!isAxiosError(err)) {
    return {
      message: err instanceof Error ? err.message : 'Something went wrong.',
      fieldErrors: {},
    };
  }
  if (!err.response) {
    return { message: 'Cannot reach the server. Is the backend running?', fieldErrors: {} };
  }

  const body = err.response.data as ApiErrorBody | undefined;
  const fieldErrors: Record<string, string> = {};
  const details = body?.error?.details;
  if (details && typeof details === 'object' && !Array.isArray(details)) {
    for (const [field, value] of Object.entries(details)) {
      const msg = firstMessage(value);
      if (msg) fieldErrors[field] = msg;
    }
  }

  const fieldSummary = Object.values(fieldErrors)[0];
  const message =
    fieldErrors.non_field_errors ??
    (body?.error?.message && body.error.message !== 'Validation failed.'
      ? body.error.message
      : (fieldSummary ?? body?.error?.message ?? `Request failed (${err.response.status}).`));

  return { message, fieldErrors, status: err.response.status };
}
