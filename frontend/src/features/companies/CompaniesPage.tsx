import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { companiesApi } from '../../api/crm';
import { parseApiError } from '../../api/errors';
import { useToast } from '../../components/Toast';
import { Button } from '../../components/ui/Button';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { DataTable, type Column } from '../../components/ui/DataTable';
import { FilterSelect, PageHeader, SearchInput, Toolbar } from '../../components/ui/misc';
import { useListParams } from '../../hooks/useListParams';
import { INDUSTRY_OPTIONS, SIZE_OPTIONS, labelOf } from '../../lib/options';
import type { Company } from '../../types';
import { useAuth } from '../auth/AuthContext';
import { CompanyFormModal } from './CompanyFormModal';

export function CompaniesPage() {
  const { hasRole } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const list = useListParams({ industry: '', size: '' }, 'name');
  const [editing, setEditing] = useState<Company | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<Company | null>(null);

  const query = useQuery({
    queryKey: [companiesApi.key, list.params],
    queryFn: () => companiesApi.list(list.params),
    placeholderData: keepPreviousData,
  });

  const remove = useMutation({
    mutationFn: (id: number) => companiesApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [companiesApi.key] });
      toast.success('Company deleted');
      setDeleting(null);
    },
    onError: (err) => toast.error(parseApiError(err).message),
  });

  const columns: Column<Company>[] = [
    {
      key: 'name',
      header: 'Name',
      sortField: 'name',
      render: (c) => (
        <div>
          <p className="font-medium">{c.name}</p>
          {c.website && (
            <a
              href={c.website}
              target="_blank"
              rel="noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="text-xs text-indigo-600 hover:underline dark:text-indigo-400"
            >
              {c.website.replace(/^https?:\/\//, '')}
            </a>
          )}
        </div>
      ),
    },
    {
      key: 'industry',
      header: 'Industry',
      sortField: 'industry',
      render: (c) => labelOf(INDUSTRY_OPTIONS, c.industry),
    },
    { key: 'size', header: 'Size', render: (c) => labelOf(SIZE_OPTIONS, c.size || null) },
    { key: 'city', header: 'City', sortField: 'city', render: (c) => c.city || '—' },
    {
      key: 'contacts',
      header: 'Contacts',
      sortField: 'contact_count',
      render: (c) => c.contact_count ?? 0,
    },
    ...(hasRole('admin')
      ? [{ key: 'owner', header: 'Owner', render: (c: Company) => c.owner_name ?? '—' }]
      : []),
    {
      key: 'actions',
      header: '',
      className: 'text-right',
      render: (c) => (
        <div className="flex justify-end gap-1">
          <Button
            variant="ghost"
            size="sm"
            aria-label={`Edit ${c.name}`}
            onClick={() => setEditing(c)}
          >
            <Pencil className="size-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            aria-label={`Delete ${c.name}`}
            onClick={() => setDeleting(c)}
          >
            <Trash2 className="size-4 text-rose-500" />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <section>
      <PageHeader
        title="Companies"
        description="The organisations your contacts work for."
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus className="size-4" /> New company
          </Button>
        }
      />
      <Toolbar>
        <SearchInput
          value={list.search}
          onChange={list.setSearch}
          placeholder="Search name, city, website"
        />
        <FilterSelect
          label="Industry"
          value={list.filters.industry}
          onChange={(v) => list.setFilter('industry', v)}
          options={INDUSTRY_OPTIONS}
        />
        <FilterSelect
          label="Size"
          value={list.filters.size}
          onChange={(v) => list.setFilter('size', v)}
          options={SIZE_OPTIONS}
        />
      </Toolbar>
      <DataTable
        columns={columns}
        rows={query.data?.results}
        rowKey={(c) => c.id}
        loading={query.isFetching}
        error={query.isError ? parseApiError(query.error).message : null}
        emptyTitle={
          list.search || list.filters.industry || list.filters.size
            ? 'No matching companies'
            : 'No companies yet'
        }
        emptyHint="Add your first company, or import contacts with a company column."
        ordering={list.ordering}
        onOrderingChange={list.setOrdering}
        page={list.page}
        total={query.data?.count}
        onPageChange={list.setPage}
      />
      <CompanyFormModal
        open={creating || editing !== null}
        company={editing}
        onClose={() => {
          setCreating(false);
          setEditing(null);
        }}
      />
      <ConfirmDialog
        open={deleting !== null}
        title="Delete company?"
        message={`"${deleting?.name}" will be deleted. Its contacts are kept but lose their company.`}
        loading={remove.isPending}
        onConfirm={() => deleting && remove.mutate(deleting.id)}
        onCancel={() => setDeleting(null)}
      />
    </section>
  );
}
