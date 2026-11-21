import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowRightCircle, Kanban, Plus, Trash2 } from 'lucide-react';
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
import { ConvertLeadModal } from './ConvertLeadModal';
import { ScoreBadge } from '../../components/ml/ScoreBadge';
import { LeadFormModal } from './LeadFormModal';

export function LeadsPage() {
  const { hasRole } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const list = useListParams({ status: '', source: '', score_label: '' }, '-score');
  const [editing, setEditing] = useState<Lead | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<Lead | null>(null);
  const [converting, setConverting] = useState<Lead | null>(null);

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
      render: (l) => (
        <ScoreBadge score={l.score} label={l.score_label} factors={l.score_explanation} />
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
        <div className="flex justify-end gap-1">
          {l.deal ? (
            <Link
              to="/pipeline"
              onClick={(e) => e.stopPropagation()}
              className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium text-emerald-700 hover:bg-emerald-50 dark:text-emerald-300 dark:hover:bg-emerald-500/10"
            >
              <Kanban className="size-4" /> View deal
            </Link>
          ) : (
            l.status !== 'converted' &&
            l.status !== 'unqualified' && (
              <Button
                variant="ghost"
                size="sm"
                aria-label={`Convert lead for ${l.contact_name} to a deal`}
                onClick={(e) => {
                  e.stopPropagation();
                  setConverting(l);
                }}
              >
                <ArrowRightCircle className="size-4 text-indigo-500" /> Convert
              </Button>
            )
          )}
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
        </div>
      ),
    },
  ];

  const filtered = Boolean(
    list.search || list.filters.status || list.filters.source || list.filters.score_label,
  );

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
        <FilterSelect
          label="Score"
          value={list.filters.score_label}
          onChange={(v) => list.setFilter('score_label', v)}
          options={[
            { value: 'hot', label: 'Hot (70+)' },
            { value: 'warm', label: 'Warm (40-69)' },
            { value: 'cold', label: 'Cold (<40)' },
          ]}
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
      {converting && <ConvertLeadModal lead={converting} onClose={() => setConverting(null)} />}
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
