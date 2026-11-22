import type { ReactNode } from 'react';

/** A titled card used for each block of the Settings page. */
export function SettingsSection({
  id,
  title,
  description,
  actions,
  children,
}: {
  id: string;
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section
      aria-labelledby={`${id}-title`}
      className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 id={`${id}-title`} className="text-base font-semibold">
            {title}
          </h2>
          {description && (
            <p className="mt-0.5 text-sm text-slate-600 dark:text-slate-400">{description}</p>
          )}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}
