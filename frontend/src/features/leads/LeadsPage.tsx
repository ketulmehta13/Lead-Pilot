import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { leadsApi } from '../../api/crm';
import { parseApiError } from '../../api/errors';
import { useToast } from '../../components/Toast';
import { Button } from '../../components/ui/Button';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { DataTable, type Column } from '../../components/ui/DataTable';
import { Badge, FilterSelect, PageHeader, SearchInput, Toolbar } from '../../components/ui/misc';
import { useListParams } from '../../hooks/useListParams';
import { formatINR, timeAgo } from '../../lib/format';
import {
  LEAD_SOURCE_OPTIONS,
  LEAD_STATUS_OPTIONS,
  LEAD_STATUS_TONE,
  labelOf,
} from '../../lib/options';
import type { Lead } from '../../types';
import { useAuth } from '../auth/AuthContext';
import { LeadFormModal } from './LeadFormModal';

export function LeadsPage() {
  const { hasRole } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const list = useListParams({ status: '', source: '' }, '-created_at');
  const [editing, setEditing] = useState<Lead | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<Lead | null>(null);

  const query = useQuery({
    queryKey: [leadsApi.key, list.params],
    queryFn: () => leadsApi.list(list.params),
    placeholderData: keepPreviousData,
  });

  const remove = useMutation({
    mutationFn: (id: number) => leadsApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [leadsApi.key] });
      toast.success('Lead deleted');
      setDeleting(null);
    },
    onError: (err) => toast.error(parseApiError(err).message),
  });

  const columns: Column<Lead>[] = [
    {
      key: 'contact',
      header: 'Lead',
      render: (l) => (
        <div>
          <Link
            to={`/contacts/${l.contact}`}
            onClick={(e) => e.stopPropagation()}
            className="font-medium hover:underline"
          >
            {l.contact_name}
          </Link>
          <p className="text-xs text-slate-500">{l.company_name ?? l.contact_email}</p>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      sortField: 'status',
      render: (l) => (
        <Badge tone={LEAD_STATUS_TONE[l.status]}>{labelOf(LEAD_STATUS_OPTIONS, l.status)}</Badge>
      ),
    },
    {
      key: 'source',
      header: 'Source',
      className: 'hidden md:table-cell',
      render: (l) => labelOf(LEAD_SOURCE_OPTIONS, l.source),
    },
    {
      key: 'budget',
      header: 'Budget',
      sortField: 'budget',
      className: 'text-right',
      render: (l) => formatINR(l.budget),
    },
    {
      key: 'score',
      header: 'Score',
      sortField: 'score',
      render: (l) =>
        l.score === null ? (
          <span className="text-xs text-slate-400" title="AI scoring arrives in Phase 3">
            Not scored
          </span>
        ) : (
          <Badge
            tone={l.score_label === 'hot' ? 'rose' : l.score_label === 'warm' ? 'amber' : 'sky'}
          >
            {l.score}
          </Badge>
        ),
    },
    {
      key: 'last_contacted',
      header: 'Last contacted',
      sortField: 'last_contacted_at',
      className: 'hidden lg:table-cell',
      render: (l) => (
        <span className="text-slate-600 dark:text-slate-400">{timeAgo(l.last_contacted_at)}</span>
      ),
    },
    ...(hasRole('admin')
      ? [
          {
            key: 'owner',
            header: 'Owner',
            className: 'hidden xl:table-cell',
            render: (l: Lead) => l.owner_name ?? '—',
          },
        ]
      : []),
    {
      key: 'actions',
      header: '',
      className: 'text-right',
      render: (l) => (
        <Button
          variant="ghost"
          size="sm"
          aria-label={`Delete lead for ${l.contact_name}`}
          onClick={(e) => {
            e.stopPropagation();
            setDeleting(l);
          }}
        >
          <Trash2 className="size-4 text-rose-500" />
        </Button>
      ),
    },
  ];

  const filtered = Boolean(list.search || list.filters.status || list.filters.source);

  return (
    <section>
      <PageHeader
        title="Leads"
        description="Potential deals. Click a row to edit."
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus className="size-4" /> New lead
          </Button>
        }
      />
      <Toolbar>
        <SearchInput
          value={list.search}
          onChange={list.setSearch}
          placeholder="Search contact, company, notes"
        />
        <FilterSelect
          label="Status"
          value={list.filters.status}
          onChange={(v) => list.setFilter('status', v)}
          options={LEAD_STATUS_OPTIONS}
        />
        <FilterSelect
          label="Source"
          value={list.filters.source}
          onChange={(v) => list.setFilter('source', v)}
          options={LEAD_SOURCE_OPTIONS}
        />
      </Toolbar>
      <DataTable
        columns={columns}
        rows={query.data?.results}
        rowKey={(l) => l.id}
        loading={query.isFetching}
        error={query.isError ? parseApiError(query.error).message : null}
        emptyTitle={filtered ? 'No matching leads' : 'No leads yet'}
        emptyHint={filtered ? undefined : 'Create a lead for one of your contacts.'}
        ordering={list.ordering}
        onOrderingChange={list.setOrdering}
        onRowClick={setEditing}
        page={list.page}
        total={query.data?.count}
        onPageChange={list.setPage}
      />
      <LeadFormModal
        open={creating || editing !== null}
        lead={editing}
        onClose={() => {
          setCreating(false);
          setEditing(null);
        }}
      />
      <ConfirmDialog
        open={deleting !== null}
        title="Delete lead?"
        message={`The lead for ${deleting?.contact_name} will be deleted. The contact is kept.`}
        loading={remove.isPending}
        onConfirm={() => deleting && remove.mutate(deleting.id)}
        onCancel={() => setDeleting(null)}
      />
    </section>
  );
}
