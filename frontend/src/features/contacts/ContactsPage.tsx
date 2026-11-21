import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { Plus, Upload } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { contactsApi } from '../../api/crm';
import { parseApiError } from '../../api/errors';
import { Button } from '../../components/ui/Button';
import { DataTable, type Column } from '../../components/ui/DataTable';
import { Badge, FilterSelect, PageHeader, SearchInput, Toolbar } from '../../components/ui/misc';
import { useListParams } from '../../hooks/useListParams';
import type { Contact } from '../../types';
import { useAuth } from '../auth/AuthContext';
import { ContactFormModal, useCompanyOptions } from './ContactFormModal';
import { ImportContactsModal } from './ImportContactsModal';

export function ContactsPage() {
  const { hasRole } = useAuth();
  const canEdit = hasRole('admin', 'sales');
  const navigate = useNavigate();
  const list = useListParams({ company: '', tag: '' }, 'first_name');
  const [creating, setCreating] = useState(false);
  const [importing, setImporting] = useState(false);
  const companies = useCompanyOptions(canEdit);

  const query = useQuery({
    queryKey: [contactsApi.key, list.params],
    queryFn: () => contactsApi.list(list.params),
    placeholderData: keepPreviousData,
  });

  const columns: Column<Contact>[] = [
    {
      key: 'name',
      header: 'Name',
      sortField: 'first_name',
      render: (c) => (
        <div>
          <p className="font-medium">{c.full_name}</p>
          <p className="text-xs text-slate-500">{c.email}</p>
        </div>
      ),
    },
    { key: 'company', header: 'Company', render: (c) => c.company_name ?? '—' },
    {
      key: 'phone',
      header: 'Phone',
      className: 'hidden md:table-cell',
      render: (c) => c.phone || '—',
    },
    {
      key: 'tags',
      header: 'Tags',
      className: 'hidden lg:table-cell',
      render: (c) =>
        c.tags.length ? (
          <div className="flex flex-wrap gap-1">
            {c.tags.map((t) => (
              <Badge key={t}>{t}</Badge>
            ))}
          </div>
        ) : (
          '—'
        ),
    },
    ...(hasRole('admin')
      ? [{ key: 'owner', header: 'Owner', render: (c: Contact) => c.owner_name ?? '—' }]
      : []),
  ];

  const filtered = Boolean(list.search || list.filters.company || list.filters.tag);

  return (
    <section>
      <PageHeader
        title="Contacts"
        description={canEdit ? 'People you sell to.' : 'Customer directory (read-only).'}
        actions={
          canEdit && (
            <>
              <Button variant="secondary" onClick={() => setImporting(true)}>
                <Upload className="size-4" /> Import CSV
              </Button>
              <Button onClick={() => setCreating(true)}>
                <Plus className="size-4" /> New contact
              </Button>
            </>
          )
        }
      />
      <Toolbar>
        <SearchInput
          value={list.search}
          onChange={list.setSearch}
          placeholder="Search name, email, phone, company"
        />
        {canEdit && (
          <FilterSelect
            label="Company"
            value={list.filters.company}
            onChange={(v) => list.setFilter('company', v)}
            options={(companies.data?.results ?? []).map((c) => ({
              value: String(c.id),
              label: c.name,
            }))}
          />
        )}
        <input
          aria-label="Filter by tag"
          placeholder="Tag"
          value={list.filters.tag}
          onChange={(e) => list.setFilter('tag', e.target.value)}
          className="block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm sm:w-32 dark:border-slate-700 dark:bg-slate-950"
        />
      </Toolbar>
      <DataTable
        columns={columns}
        rows={query.data?.results}
        rowKey={(c) => c.id}
        loading={query.isFetching}
        error={query.isError ? parseApiError(query.error).message : null}
        emptyTitle={filtered ? 'No matching contacts' : 'No contacts yet'}
        emptyHint={
          !filtered && canEdit ? 'Add a contact or import a CSV to get started.' : undefined
        }
        ordering={list.ordering}
        onOrderingChange={list.setOrdering}
        onRowClick={(c) => navigate(`/contacts/${c.id}`)}
        page={list.page}
        total={query.data?.count}
        onPageChange={list.setPage}
      />
      <ContactFormModal
        open={creating}
        onClose={() => setCreating(false)}
        onSaved={(c) => navigate(`/contacts/${c.id}`)}
      />
      {importing && <ImportContactsModal open onClose={() => setImporting(false)} />}
    </section>
  );
}
