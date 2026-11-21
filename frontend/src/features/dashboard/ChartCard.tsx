import { Table2 } from 'lucide-react';
import { useId, useState } from 'react';
import type { ReactNode } from 'react';

interface Props {
  title: string;
  subtitle?: string;
  /** Rows for the "Show data" table: first column is the label. */
  table: { headers: string[]; rows: (string | number)[][] };
  children: ReactNode;
  className?: string;
}

/** Card wrapping a chart, with an accessible data-table view of the same numbers. */
export function ChartCard({ title, subtitle, table, children, className = '' }: Props) {
  const [showTable, setShowTable] = useState(false);
  const tableId = useId();
  return (
    <figure
      className={`rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900 ${className}`}
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <figcaption>
          <h2 className="font-semibold">{title}</h2>
          {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
        </figcaption>
        <button
          type="button"
          aria-expanded={showTable}
          aria-controls={tableId}
          onClick={() => setShowTable((v) => !v)}
          className="inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-xs text-slate-500 hover:bg-slate-100 hover:text-slate-800 dark:hover:bg-slate-800 dark:hover:text-slate-200"
        >
          <Table2 className="size-3.5" aria-hidden />
          {showTable ? 'Show chart' : 'Show data'}
        </button>
      </div>
      {showTable ? (
        <div id={tableId} className="max-h-72 overflow-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-slate-500">
              <tr>
                {table.headers.map((h, i) => (
                  <th key={h} scope="col" className={`py-1.5 font-medium ${i ? 'text-right' : ''}`}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {table.rows.map((row) => (
                <tr key={String(row[0])}>
                  {row.map((cell, i) => (
                    <td key={i} className={`py-1.5 ${i ? 'text-right tabular-nums' : ''}`}>
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="h-64" aria-hidden>
          {children}
        </div>
      )}
    </figure>
  );
}

/** Tooltip box shared by all dashboard charts (text in ink colours, never the series colour). */
export function TooltipBox({ title, lines }: { title: string; lines: string[] }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-md dark:border-slate-700 dark:bg-slate-800">
      <p className="font-medium text-slate-900 dark:text-slate-100">{title}</p>
      {lines.map((line) => (
        <p key={line} className="text-slate-600 tabular-nums dark:text-slate-300">
          {line}
        </p>
      ))}
    </div>
  );
}
