import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { invoicesApi } from '../../api/billing';
import { parseApiError } from '../../api/errors';
import { Button } from '../../components/ui/Button';
import { DataTable, type Column } from '../../components/ui/DataTable';
import { FilterSelect, PageHeader, SearchInput, Toolbar } from '../../components/ui/misc';
import { useListParams } from '../../hooks/useListParams';
import { formatDate, formatINR } from '../../lib/format';
import type { Invoice } from '../../types';
import { InvoiceBuilderModal } from './InvoiceBuilderModal';
import { InvoiceStatusBadge } from './InvoiceStatusBadge';

const STATUS_OPTIONS = [
  { value: 'draft', label: 'Draft' },
  { value: 'sent', label: 'Sent' },
  { value: 'processing', label: 'Processing' },
  { value: 'paid', label: 'Paid' },
  { value: 'failed', label: 'Payment failed' },
  { value: 'refunded', label: 'Refunded' },
];

export function InvoicesPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const dealFromLink = Number(searchParams.get('deal')) || null;
  const [building, setBuilding] = useState(dealFromLink !== null);
  const list = useListParams({ status: '' }, '-created_at');

  const query = useQuery({
    queryKey: [invoicesApi.key, list.params],
    queryFn: () => invoicesApi.list(list.params),
    placeholderData: keepPreviousData,
  });

  const columns: Column<Invoice>[] = [
    {
      key: 'number',
      header: 'Invoice',
      sortField: 'number',
      render: (i) => (
        <div>
          <p className="font-medium tabular-nums">{i.number}</p>
          <p className="text-xs text-slate-500">{i.deal_title}</p>
        </div>
      ),
    },
    {
      key: 'customer',
      header: 'Customer',
      render: (i) => (
        <div>
          <p>{i.contact_name}</p>
          <p className="text-xs text-slate-500">{i.company_name ?? i.contact_email}</p>
        </div>
      ),
    },
    { key: 'status', header: 'Status', render: (i) => <InvoiceStatusBadge status={i.status} /> },
    {
      key: 'total',
      header: 'Total',
      sortField: 'total',
      className: 'text-right',
      render: (i) => <span className="tabular-nums">{formatINR(i.total)}</span>,
    },
    {
      key: 'date',
      header: 'Date',
      sortField: 'created_at',
      className: 'hidden md:table-cell',
      render: (i) =>
        i.paid_at ? (
          <span className="text-emerald-700 dark:text-emerald-400">
            Paid {formatDate(i.paid_at)}
          </span>
        ) : (
          <span className="text-slate-600 dark:text-slate-400">
            {formatDate(i.created_at)}
            {i.due_date ? ` · due ${formatDate(i.due_date)}` : ''}
          </span>
        ),
    },
  ];

  return (
    <section>
      <PageHeader
        title="Invoices"
        description="Bill won deals and collect payment with Razorpay (test mode)."
        actions={
          <Button onClick={() => setBuilding(true)}>
            <Plus className="size-4" /> New invoice
          </Button>
        }
      />
      <Toolbar>
        <SearchInput
          value={list.search}
          onChange={list.setSearch}
          placeholder="Search number, customer, deal"
        />
        <FilterSelect
          label="Status"
          value={list.filters.status}
          onChange={(v) => list.setFilter('status', v)}
          options={STATUS_OPTIONS}
        />
      </Toolbar>
      <DataTable
        columns={columns}
        rows={query.data?.results}
        rowKey={(i) => i.id}
        loading={query.isFetching}
        error={query.isError ? parseApiError(query.error).message : null}
        emptyTitle={list.search || list.filters.status ? 'No matching invoices' : 'No invoices yet'}
        emptyHint="Create one from a won deal."
        ordering={list.ordering}
        onOrderingChange={list.setOrdering}
        onRowClick={(i) => navigate(`/invoices/${i.id}`)}
        page={list.page}
        total={query.data?.count}
        onPageChange={list.setPage}
      />
      {building && (
        <InvoiceBuilderModal
          initialDealId={dealFromLink}
          onClose={() => {
            setBuilding(false);
            if (dealFromLink) setSearchParams({}, { replace: true });
          }}
        />
      )}
    </section>
  );
}
