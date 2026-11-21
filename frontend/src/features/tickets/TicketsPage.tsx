import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { MessageSquare, Plus } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { parseApiError } from '../../api/errors';
import { ticketsApi } from '../../api/support';
import { Button } from '../../components/ui/Button';
import { DataTable, type Column } from '../../components/ui/DataTable';
import { FilterSelect, PageHeader, SearchInput, Toolbar } from '../../components/ui/misc';
import { useListParams } from '../../hooks/useListParams';
import { timeAgo } from '../../lib/format';
import { TICKET_PRIORITY_OPTIONS, TICKET_STATUS_OPTIONS, labelOf } from '../../lib/options';
import type { Ticket } from '../../types';
import { useAuth } from '../auth/AuthContext';
import { PriorityBadge, SentimentBadge } from './badges';
import { TicketDetailModal } from './TicketDetailModal';
import { TicketFormModal } from './TicketFormModal';

export function TicketsPage() {
  const { hasRole } = useAuth();
  const canEdit = hasRole('admin', 'support');
  const list = useListParams({ open: 'true', priority: '', sentiment: '' });
  const [creating, setCreating] = useState(false);
  const [viewing, setViewing] = useState<Ticket | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const linkedId = Number(searchParams.get('ticket')) || null;

  // Citation links from Ask LeadPilot open a ticket directly: /tickets?ticket=<id>
  useEffect(() => {
    if (!linkedId) return;
    let cancelled = false;
    ticketsApi
      .get(linkedId)
      .then((t) => !cancelled && setViewing(t))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [linkedId]);

  const closeViewing = () => {
    setViewing(null);
    if (linkedId) setSearchParams({}, { replace: true });
  };

  const query = useQuery({
    queryKey: [ticketsApi.key, list.params],
    queryFn: () => ticketsApi.list(list.params),
    placeholderData: keepPreviousData,
  });

  const columns: Column<Ticket>[] = [
    {
      key: 'priority',
      header: 'Priority',
      sortField: 'priority_rank',
      render: (t) => <PriorityBadge priority={t.priority} urgent={t.urgent} />,
    },
    {
      key: 'subject',
      header: 'Ticket',
      render: (t) => (
        <div>
          <p className="font-medium">{t.subject}</p>
          <p className="text-xs text-slate-500">
            {t.contact_name}
            {t.company_name ? ` · ${t.company_name}` : ''}
          </p>
        </div>
      ),
    },
    {
      key: 'sentiment',
      header: 'Sentiment',
      sortField: 'sentiment_score',
      render: (t) => <SentimentBadge sentiment={t.sentiment} score={t.sentiment_score} />,
    },
    {
      key: 'status',
      header: 'Status',
      className: 'hidden md:table-cell',
      render: (t) => labelOf(TICKET_STATUS_OPTIONS, t.status),
    },
    {
      key: 'age',
      header: 'Opened',
      sortField: 'created_at',
      className: 'hidden lg:table-cell',
      render: (t) => (
        <span className="inline-flex items-center gap-2 text-slate-600 dark:text-slate-400">
          {timeAgo(t.created_at)}
          {t.comment_count > 0 && (
            <span className="inline-flex items-center gap-0.5 text-xs" title="Comments">
              <MessageSquare className="size-3" aria-hidden />
              {t.comment_count}
            </span>
          )}
        </span>
      ),
    },
  ];

  return (
    <section>
      <PageHeader
        title="Tickets"
        description={
          canEdit
            ? 'Support queue, most urgent first. Priority is set automatically from the text.'
            : 'Support tickets for your contacts (read-only).'
        }
        actions={
          canEdit && (
            <Button onClick={() => setCreating(true)}>
              <Plus className="size-4" /> New ticket
            </Button>
          )
        }
      />
      <Toolbar>
        <SearchInput value={list.search} onChange={list.setSearch} placeholder="Search tickets" />
        <FilterSelect
          label="State"
          value={list.filters.open}
          onChange={(v) => list.setFilter('open', v)}
          options={[
            { value: 'true', label: 'Open + in progress' },
            { value: 'false', label: 'Resolved + closed' },
          ]}
        />
        <FilterSelect
          label="Priority"
          value={list.filters.priority}
          onChange={(v) => list.setFilter('priority', v)}
          options={TICKET_PRIORITY_OPTIONS}
        />
        <FilterSelect
          label="Sentiment"
          value={list.filters.sentiment}
          onChange={(v) => list.setFilter('sentiment', v)}
          options={[
            { value: 'negative', label: 'Negative' },
            { value: 'neutral', label: 'Neutral' },
            { value: 'positive', label: 'Positive' },
          ]}
        />
      </Toolbar>
      <DataTable
        columns={columns}
        rows={query.data?.results}
        rowKey={(t) => t.id}
        loading={query.isFetching}
        error={query.isError ? parseApiError(query.error).message : null}
        emptyTitle="No tickets here"
        ordering={list.ordering}
        onOrderingChange={list.setOrdering}
        onRowClick={setViewing}
        page={list.page}
        total={query.data?.count}
        onPageChange={list.setPage}
      />
      {creating && <TicketFormModal onClose={() => setCreating(false)} />}
      {viewing && <TicketDetailModal ticket={viewing} canEdit={canEdit} onClose={closeViewing} />}
    </section>
  );
}
