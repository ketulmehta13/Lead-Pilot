import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Inbox } from 'lucide-react';
import type { ReactNode } from 'react';
import { Spinner } from './Spinner';

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  /** API ordering field; makes the header clickable. */
  sortField?: string;
  className?: string;
}

interface Props<T> {
  columns: Column<T>[];
  rows: T[] | undefined;
  rowKey: (row: T) => number | string;
  loading?: boolean;
  error?: string | null;
  emptyTitle?: string;
  emptyHint?: ReactNode;
  ordering?: string;
  onOrderingChange?: (ordering: string) => void;
  onRowClick?: (row: T) => void;
  /** Pagination */
  page?: number;
  pageSize?: number;
  total?: number;
  onPageChange?: (page: number) => void;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  loading,
  error,
  emptyTitle = 'Nothing here yet',
  emptyHint,
  ordering = '',
  onOrderingChange,
  onRowClick,
  page = 1,
  pageSize = 20,
  total,
  onPageChange,
}: Props<T>) {
  const sortBy = (field: string) => {
    if (!onOrderingChange) return;
    onOrderingChange(ordering === field ? `-${field}` : field);
  };

  let body: ReactNode;
  if (loading && !rows) {
    body = (
      <div className="flex justify-center py-16">
        <Spinner />
      </div>
    );
  } else if (error) {
    body = <p className="py-16 text-center text-sm text-rose-600">{error}</p>;
  } else if (!rows || rows.length === 0) {
    body = (
      <div className="flex flex-col items-center py-16 text-center">
        <Inbox className="size-9 text-slate-300 dark:text-slate-600" aria-hidden />
        <p className="mt-3 font-medium">{emptyTitle}</p>
        {emptyHint && <div className="mt-1 text-sm text-slate-500">{emptyHint}</div>}
      </div>
    );
  }

  const pages = total ? Math.max(1, Math.ceil(total / pageSize)) : 1;

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      {body ?? (
        <div className={`overflow-x-auto ${loading ? 'opacity-60' : ''}`}>
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs font-medium tracking-wide text-slate-500 uppercase dark:border-slate-800 dark:bg-slate-900/60">
              <tr>
                {columns.map((col) => {
                  const active = ordering.replace('-', '') === col.sortField;
                  return (
                    <th key={col.key} scope="col" className={`px-4 py-3 ${col.className ?? ''}`}>
                      {col.sortField && onOrderingChange ? (
                        <button
                          type="button"
                          onClick={() => sortBy(col.sortField!)}
                          className="inline-flex items-center gap-1 uppercase hover:text-slate-800 dark:hover:text-slate-200"
                        >
                          {col.header}
                          {active &&
                            (ordering.startsWith('-') ? (
                              <ArrowDown className="size-3" aria-label="descending" />
                            ) : (
                              <ArrowUp className="size-3" aria-label="ascending" />
                            ))}
                        </button>
                      ) : (
                        col.header
                      )}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {rows!.map((row) => (
                <tr
                  key={rowKey(row)}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  className={
                    onRowClick ? 'cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50' : ''
                  }
                >
                  {columns.map((col) => (
                    <td key={col.key} className={`px-4 py-3 align-middle ${col.className ?? ''}`}>
                      {col.render(row)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {onPageChange && total !== undefined && total > 0 && (
        <div className="flex items-center justify-between border-t border-slate-200 px-4 py-2.5 text-sm text-slate-600 dark:border-slate-800 dark:text-slate-400">
          <span>
            {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total}
          </span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              aria-label="Previous page"
              disabled={page <= 1}
              onClick={() => onPageChange(page - 1)}
              className="rounded-md p-1.5 hover:bg-slate-100 disabled:opacity-40 dark:hover:bg-slate-800"
            >
              <ChevronLeft className="size-4" />
            </button>
            <span className="px-1">
              {page} / {pages}
            </span>
            <button
              type="button"
              aria-label="Next page"
              disabled={page >= pages}
              onClick={() => onPageChange(page + 1)}
              className="rounded-md p-1.5 hover:bg-slate-100 disabled:opacity-40 dark:hover:bg-slate-800"
            >
              <ChevronRight className="size-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
