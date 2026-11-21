import { forwardRef, useId } from 'react';
import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from 'react';

export const controlClass =
  'block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-xs placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 focus:outline-none disabled:opacity-60 aria-invalid:border-rose-500 dark:border-slate-700 dark:bg-slate-950';

interface WrapperProps {
  label: string;
  error?: string;
  hint?: string;
  required?: boolean;
  children: (id: string, describedBy: string | undefined) => ReactNode;
}

function FieldWrapper({ label, error, hint, required, children }: WrapperProps) {
  const id = useId();
  const messageId = `${id}-msg`;
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium">
        {label}
        {required && <span className="text-rose-500"> *</span>}
      </label>
      {children(id, error || hint ? messageId : undefined)}
      {error ? (
        <p id={messageId} className="mt-1 text-xs text-rose-600 dark:text-rose-400">
          {error}
        </p>
      ) : hint ? (
        <p id={messageId} className="mt-1 text-xs text-slate-500">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

type Common = { label: string; error?: string; hint?: string };

export const TextField = forwardRef<
  HTMLInputElement,
  Common & InputHTMLAttributes<HTMLInputElement>
>(function TextField({ label, error, hint, required, className = '', ...rest }, ref) {
  return (
    <FieldWrapper label={label} error={error} hint={hint} required={required}>
      {(id, describedBy) => (
        <input
          ref={ref}
          id={id}
          aria-invalid={Boolean(error)}
          aria-describedby={describedBy}
          className={`${controlClass} ${className}`}
          {...rest}
        />
      )}
    </FieldWrapper>
  );
});

export const SelectField = forwardRef<
  HTMLSelectElement,
  Common & SelectHTMLAttributes<HTMLSelectElement> & { options: { value: string; label: string }[] }
>(function SelectField({ label, error, hint, required, options, className = '', ...rest }, ref) {
  return (
    <FieldWrapper label={label} error={error} hint={hint} required={required}>
      {(id, describedBy) => (
        <select
          ref={ref}
          id={id}
          aria-invalid={Boolean(error)}
          aria-describedby={describedBy}
          className={`${controlClass} ${className}`}
          {...rest}
        >
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      )}
    </FieldWrapper>
  );
});

export const TextAreaField = forwardRef<
  HTMLTextAreaElement,
  Common & TextareaHTMLAttributes<HTMLTextAreaElement>
>(function TextAreaField({ label, error, hint, required, className = '', ...rest }, ref) {
  return (
    <FieldWrapper label={label} error={error} hint={hint} required={required}>
      {(id, describedBy) => (
        <textarea
          ref={ref}
          id={id}
          rows={4}
          aria-invalid={Boolean(error)}
          aria-describedby={describedBy}
          className={`${controlClass} ${className}`}
          {...rest}
        />
      )}
    </FieldWrapper>
  );
});
